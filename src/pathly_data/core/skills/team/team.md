# team

Unified entry point for the Pathly team pipeline.
HTTP/FSM engine first (auto-starts the Python server via `fsm-call`); falls back to
the LLM orchestrator if the server cannot start. Use `team-http` to force HTTP-only.

Run for `$ARGUMENTS`.

## Argument parsing

Parse `$ARGUMENTS` (order doesn't matter):
- First non-keyword word = `FEATURE`
- `lite` → `rigor = lite` | `standard` → `rigor = standard` | `strict` → `rigor = strict`
- `nano` → `mode = nano`
- `fast` → `autoFlow = true`
- `plan` → `entryStage = plan` | `build` → `entryStage = build` | `test` → `entryStage = test`
- Defaults: `entryStage = discovery`, `rigor = lite`

### Guard — Feature name validation

After parsing, validate `FEATURE` before continuing:
- If `FEATURE` contains spaces, newlines, tabs, or is longer than 50 characters: stop →
  ```
  Invalid feature name. Use a short slug, e.g. "fix-hooks" or "auth-refactor".
  Re-run: /pathly-team <feature-name> [fast|lite|standard|strict]
  ```
- If `FEATURE` was derived from auto-detection (not from `$ARGUMENTS`), confirm with the user before proceeding.

## Feature detection

If no `FEATURE` was found in `$ARGUMENTS`, auto-detect:
1. Read `pathly/plans/*/STATE.json` files, sorted by modification time (newest first).
   Use the most recent feature whose state is not `IDLE` or `DONE`.
2. If none found, use the most recently modified `pathly/plans/*/` folder (excluding `.archive/`).
3. If multiple candidates exist: list them numbered and ask "Which feature? [1/2/…]"
4. If no `pathly/plans/` folder exists or is empty: stop →
   `No active feature found. Start with /pathly go to describe what you want to build.`

Conflict checks (stop and report):
- `strict` + `fast` → `strict mode requires human approval gates; remove fast or choose standard fast.`
- `nano` + `strict|standard|plan|build|test` → `nano mode has no plan stages; remove the conflicting flag or choose lite instead.`

## Mode selection

If `fast` was parsed from `$ARGUMENTS`, set `autoFlow = true` and skip this step.

Otherwise ask the user:

```
Choose execution mode:

1. Auto-flow — implement, review, then commit and continue automatically
   (Commits only after the reviewer passes — not after every build.)

2. Manual — run one stage at a time; you decide when to commit
```

Wait for reply. Default to Manual if unclear. Store as `autoFlow`.

---

## Design system check

Before spawning any engine, check for `pathly/plans/<feature>/DESIGN.md`:

- **If it exists** → print: `Design system found: pathly/plans/<feature>/DESIGN.md ✓`
- **If it does not exist** and `entryStage` is `discovery` or `build` → print:
  ```
  No DESIGN.md found for <feature>.
  If this feature includes UI work, run /pathly design first to generate a visual spec.
  (Skip this if the feature is backend-only.)
  ```
  Do not block — continue regardless of the user's choice.

---

## Nano mode

If `mode = nano`, run inline — do not route to any engine.

**Step 1 — Ask for task:**
```
Nano mode active. Describe the change in one sentence:
(Builder will implement directly with no plan. Scope: ≤ 2 files.)
```
Store reply as `NANO_TASK`.

**Step 2 — Spawn builder:**
```
Nano task: [NANO_TASK]
Make only the changes needed. Touch at most 2 files.
If the fix requires touching more than 2 files, STOP immediately and report:
  "Scope too large for nano — recommend upgrading to route `flow [feature] lite`"
Do not create any plan files.
Verify with the project's standard verify command when done.
Report: files changed, verify result.
```

**Step 3 — Scope check:** Run `git diff --name-only HEAD`. Count changed files (exclude `pathly/plans/`).
If count > 2 and builder did not escalate:
```
[NANO ESCALATION] Builder touched N files (nano limit is 2).
[1] Accept — proceed with review as-is
[2] Upgrade — restart as `flow [feature] lite`
[3] Cancel
```
On [2] or [3]: stop.

**Step 4 — Spawn reviewer:**
```
Review the nano change for [feature].
Run: git diff HEAD (or git diff --staged if not yet committed).
Check for correctness, obvious bugs, and rule violations.
Report: PASS or list each violation with file + line.
Do not write feedback files — report violations inline.
```

**Step 5 — Fix cycle (max 1):** If violations found, spawn builder with the list. One pass only.
If violations remain after 1 pass: stop, recommend upgrading to lite.
If PASS: print `[Nano complete] [feature] done. Files changed: [list from git diff]`. Exit.

---

## Engine selection

> Skip if `mode = nano` (handled above).

Attempt a health check:

```bash
curl -s --max-time 2 http://127.0.0.1:8765/health
```

- Returns `{"status":"ok"}` → use **HTTP FSM engine** below.
- Times out or fails → run in background:
  ```bash
  python -m pathly_orchestrator.http_server &
  ```
  Wait 2 seconds, retry health check once.
  - Now returns `{"status":"ok"}` → use **HTTP FSM engine** below.
  - Still unavailable → print:
    ```
    FSM server unavailable — falling back to LLM orchestrator.
    To use the HTTP engine: run `python -m pathly_orchestrator.http_server` in a separate terminal.
    ```
    → use **LLM engine** below.

---

## HTTP FSM engine

`PROJECT_ROOT` = absolute path to cwd at skill invocation.

### Step 1 — Get next action

Invoke the `fsm-call` skill with:
```json
{"action":"next_action","flow":"team","topic":"<FEATURE>","project_root":"<PROJECT_ROOT>"}
```

Receives one of:
- `{current_state, agent, instructions, storage_path, limits}` — normal routing
- `{blocked: true, target_agent: "human", file, instructions, limits}` — human must decide
- `{blocked: true, target_agent: <agent>, file, instructions, limits}` — feedback to resolve

### Step 2 — Display contextual menu

After every `fsm-call` result, display the contextual menu before running any agent:

```
─────────────────────────────────────────────────────────
  Pathly  ·  team  ·  <FEATURE>
  State : <current_state>    Conv : <conv>    Mode : <manual|auto-flow>
  Agent : <agent>
─────────────────────────────────────────────────────────
  Pipeline:
    <states with ✓ for completed, [ ] for current, lowercase for future>
─────────────────────────────────────────────────────────
  <state-specific guidance from table below>
─────────────────────────────────────────────────────────
  Options:
    [1] Proceed   — run <agent> now
    [2] Pause     — save state and stop
    [3] Status    — print STATE.json + last 10 events
    [4] Switch    — jump to /debug or /explore instead
─────────────────────────────────────────────────────────
  Reply [1–4] or press Enter to proceed:
```

When blocked by feedback (not human):
```
    [1] Resolve   — run <agent> on <file> now
    [2] View      — print <file> contents
    [3] Escalate  — write HUMAN_QUESTIONS.md and halt
    [4] Pause     — save state and stop
```

When `complete_stage` returns `{decide: true, ...}`: display Panel A, wait for reply,
invoke `fsm-call` with `complete_stage` + `decision=<reply>`, display Panel B.

**State-specific guidance:**

| State | Guidance |
|-------|----------|
| STORMING | Architect discovers scope and risks. No implementation yet. |
| PLANNING | Planner drafts IMPLEMENTATION_PLAN.md. Builder waits for it. |
| BUILDING | Builder implements the plan. Reviewer runs automatically after. |
| REVIEWING | Reviewer checks builder output. REVIEW_FAILURES.md blocks advance. |
| TESTING | Tester validates. TEST_FAILURES.md loops back to builder. |
| RETRO | Final retrospective. Topic closes when complete. |
| DONE | Topic complete. Artifacts archived. |

**Pipeline progress line:** Read EVENTS.jsonl STATE_TRANSITION entries.
Current state is bracketed `[ STATE ]`. Completed states get `✓`. Future states are lowercase.

If user chooses [2] Pause: call `pause` skill and stop.
If user chooses [3]: print STATE.json + last 10 EVENTS.jsonl lines.
If user chooses [4]: surface `/pathly team|debug|explore <FEATURE>` options.
In auto-flow mode, default to [1] without asking. Note "auto-flow: proceeding".

### Step 3 — Execute agent instructions

Execute the instructions returned by the `next_action` result for the returned agent.

Track per stage (reset each stage):
- `needs_context_count = 0`
- `feedback_round_count = 0`

**NEEDS_CONTEXT loop:**
1. `needs_context_count += 1`
2. If `>= limits.needs_context_per_stage`: warn and halt.
3. Else: call `scout-path`, feed summary back, resume.
The FSM is NOT notified about NEEDS_CONTEXT cycles.

### Step 4 — Complete the stage

Invoke the `fsm-call` skill with:
```json
{"action":"complete_stage","flow":"team","topic":"<FEATURE>","project_root":"<PROJECT_ROOT>"}
```
Add `decision` or `resolved_files` fields when applicable.

Receives one of:
- `{next_state, agent, instructions, limits}` — advance
- `{done: true}` — pipeline complete
- `{blocked: true, target_agent: "human", file, instructions}` — human must decide
- `{blocked: true, target_agent: <agent>, file, instructions}` — feedback to resolve
- `{decide: true, question, context, options, default}` — Level 3 routing

**Feedback resolution loop:**
- `feedback_round_count += 1`
- If `>= limits.feedback_rounds_per_stage`: write HUMAN_QUESTIONS.md, halt.
- Else: spawn feedback agent, resolve, invoke `fsm-call` with `complete_stage` + `resolved_files=[file]`.
- Python deletes the file. Do NOT delete files manually.
- One file at a time.

**Human-blocked:** Surface instructions to user. When user confirms, invoke `fsm-call` with
`complete_stage` + `resolved_files=["HUMAN_QUESTIONS.md"]`.

### Step 5 — Repeat

Repeat Steps 1–4 until `done=true`.

---

## LLM engine (orchestrator agent)

Spawn the **orchestrator** agent with **exactly these 5 parameters and nothing else**:
- flow_config: src/pathly_data/core/flows/team.flow.yaml
- topic: [parsed feature name]
- rigor: [parsed rigor]
- autoFlow: [true/false]
- entryStage: [parsed entryStage, default: discovery]

**CRITICAL:** Pass ONLY the 5 parameters above. Do NOT include feature descriptions,
file paths, implementation details, or conversation history. The FSM discovers all
context through its own agents. Passing extra context bypasses the flow and breaks
the pipeline.

The orchestrator handles all FSM state recovery, routing, git commits, PROGRESS.md updates,
and artifact archiving. Do not perform these actions in team.md.
