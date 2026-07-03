# dispatch

Deterministic relay — routes the current pipeline stage to the correct CLI adapter
based on the `preferred_adapter` field from `/next_action`.

Called after a `/next_action` response is received. Either executes the stage
instructions locally (Case A) or emits a handoff packet for a different adapter
(Case B). Never spawns processes; never modifies instructions.

## Arguments

`$ARGUMENTS` is a JSON object:
- `feature` (required): feature slug matching the `pathly/features/` folder, e.g. `"my-feature"`
- `current_adapter` (required): adapter this skill is running in — `"claude"`, `"codex"`, or `"copilot"`
- `flow` (optional): flow name (default: `"team"`)
- `project_root` (optional): absolute path to the project directory (default: cwd)

## Step 1 — Get /next_action

Invoke the `fsm-call` skill with:
```json
{"action":"next_action","flow":"<flow>","topic":"<feature>","project_root":"<project_root>"}
```

Parse the response. Extract:
- `preferred_adapter` — string. If the field is absent or its value is `""`: treat as `""`.
- `instructions` — the verbatim agent prompt. Use `agent_hint.instructions` if that sub-object
  is present in the response; otherwise fall back to the top-level `instructions` field.
  Do not reword, summarize, or shorten this string under any circumstances.
- `storage_path` — the feature plan directory path.
- `current_state` — the FSM state being handled.

## Step 2 — Validate preferred_adapter

Known adapters: `claude`, `codex`, `copilot`.

If `preferred_adapter` is non-empty and not in the known set:
```
dispatch: unknown adapter "<preferred_adapter>" — executing locally (Case A).
```
Treat as `""` and proceed to Case A.

## Step 3 — Route

### Case A — Execute locally

**When:** `preferred_adapter == ""` OR `preferred_adapter == current_adapter`

Execute the instructions verbatim — follow the agent prompt exactly as written.
Emit no routing output; behave as though the dispatch skill was not invoked.

### Case B — Handoff to a different adapter

**When:** `preferred_adapter` is non-empty AND differs from `current_adapter`

Do NOT execute the instructions. Print the following handoff packet exactly:

```
╔══════════════════════════════════════════════════════╗
  PATHLY HANDOFF — route this stage to: <preferred_adapter>
╚══════════════════════════════════════════════════════╝

Feature         : <feature>
State           : <current_state>
Storage path    : <storage_path>
Target adapter  : <preferred_adapter>
Current adapter : <current_adapter>

⚠  If <preferred_adapter> is not installed, paste the Instructions block into
   any available adapter — it will run correctly in any environment.
   Do not silently skip the stage.

─── Instructions (VERBATIM — paste exactly as shown, no changes) ──────────────
<instructions — copied character for character from the /next_action response>
────────────────────────────────────────────────────────────────────────────────

To continue:
  1. Open <preferred_adapter> in its IDE or terminal.
  2. Paste the Instructions block above as a new prompt.
  3. The target adapter resumes from FSM state: <current_state>
  4. When the stage completes, return here and run:
       /pathly team <feature>
     to advance the FSM to the next state.
```

## Rules

- **Never reword instructions.** The `instructions` field is a Pathly role contract — any
  change, even a single word, can break downstream agents or misroute the FSM.
- **Never spawn a process or shell out to the target adapter.** This skill is a relay only.
- **Absent `preferred_adapter` field:** treat as `""` — execute locally (Case A). Older FSM
  versions that predate multi-adapter routing omit the field entirely; this skill must be
  backward-compatible.
- **Default to Case A when uncertain.** The pipeline must never block because of this skill.
