# team-http

Runs the Pathly team pipeline via the FSM HTTP server (explicit HTTP-only mode).
All FSM calls are delegated to the `fsm-call` skill.
Use `/pathly team` instead for the standard entry point (HTTP-first with LLM fallback).

Run for `$ARGUMENTS`.

## Argument parsing

Parse `$ARGUMENTS` (order doesn't matter):
- First non-keyword word = `FEATURE`
- `lite` → `rigor = lite` | `standard` → `rigor = standard` | `strict` → `rigor = strict`
- `fast` → `autoFlow = true`
- `plan` → `entryStage = plan` | `build` → `entryStage = build` | `test` → `entryStage = test`
- Defaults: `entryStage = discovery`, `rigor = lite`

`PROJECT_ROOT` = the absolute path to the user's project directory (cwd at skill invocation).

### Guard — Feature name validation

- If `FEATURE` contains spaces, newlines, tabs, or is longer than 50 characters: stop →
  ```
  Invalid feature name. Use a short slug, e.g. "fix-hooks" or "auth-refactor".
  Re-run: /pathly-team-http <feature-name> [fast|lite|standard|strict]
  ```

## Mode selection

If `fast` was parsed, set `autoFlow = true` and skip this step.

Otherwise ask:

```
Choose execution mode:

1. Auto-flow — implement, review, then commit and continue automatically
   (Commits only after the reviewer passes — not after every build.)

2. Manual — run one stage at a time; you decide when to commit
```

Wait for reply. Default to Manual if unclear. Store as `autoFlow`.

---

## FSM engine loop

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
  Pathly  ·  team-http  ·  <FEATURE>
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
