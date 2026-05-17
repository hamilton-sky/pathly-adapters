# team

Thin orchestrator for the full feature pipeline. Recovers FSM state and routes to the
correct sub-skill. Adapters render route names in their host-native form.

Run for `$ARGUMENTS`.

## Argument parsing

Parse `$ARGUMENTS` (order doesn't matter):
- First non-keyword word = `FEATURE`
- `lite` → `rigor = lite` | `standard` → `rigor = standard` | `strict` → `rigor = strict`
- `nano` → `mode = nano`
- `fast` → `autoFlow = true`
- `plan` → `entryStage = plan` | `build` → `entryStage = build` | `test` → `entryStage = test`
- Defaults: `entryStage = discovery`, `rigor = lite`

### Guard 1 — Feature name validation

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

## FSM execution loop

After mode selection is complete (autoFlow is set), run the FSM loop using MCP tools.

`PROJECT_ROOT` = the absolute path to the user's project directory (cwd at skill invocation).

### Step 1 — Get next action

Call FSM tool: `{{FSM_NEXT_ACTION}}(flow="team", topic=FEATURE, project_root=PROJECT_ROOT)`

Receives one of:
- `{current_state, agent, instructions, storage_path, limits}` — normal routing
- `{blocked: true, target_agent: "human", file, instructions, limits}` — human must decide
- `{blocked: true, target_agent: <agent>, file, instructions, limits}` — feedback to resolve

### Step 2 — Display contextual menu

After every `{{FSM_NEXT_ACTION}}` or `{{FSM_COMPLETE_STAGE}}` call, display the contextual
menu before running any agent. Use the format exactly as specified in
`pathly/plans/mcp-fsm-driver/CONTEXTUAL_MENU_UX.md`:

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

When blocked by feedback (not human), swap option set per CONTEXTUAL_MENU_UX.md Scenario 2:
```
    [1] Resolve   — run <agent> on <file> now
    [2] View      — print <file> contents
    [3] Escalate  — write HUMAN_QUESTIONS.md and halt
    [4] Pause     — save state and stop
```

When `complete_stage` returns `{decide: true, ...}` (Level 3 routing), display Scenario 3
Panel A from CONTEXTUAL_MENU_UX.md. Wait for reply. Call
`{{FSM_COMPLETE_STAGE}}(..., decision=<reply>)`. Display Panel B.

**State-specific guidance lines:**

| State | Guidance |
|-------|----------|
| STORMING | Architect discovers scope and risks. No implementation yet. |
| PLANNING | Planner drafts IMPLEMENTATION_PLAN.md. Builder waits for it. |
| BUILDING | Builder implements the plan. Reviewer runs automatically after. |
| REVIEWING | Reviewer checks builder output. REVIEW_FAILURES.md blocks advance. |
| TESTING | Tester validates. TEST_FAILURES.md loops back to builder. |
| RETRO | Final retrospective. Topic closes when complete. |
| DONE | Topic complete. Artifacts archived. |

**Pipeline progress line:** Read EVENTS.jsonl STATE_TRANSITION entries to determine completed states.
Current state is bracketed `[ STATE ]`. Completed states get `✓`. Future states are lowercase.

If user chooses [2] Pause: call `pause` skill and stop.
If user chooses [3]: print STATE.json pretty-printed and last 10 EVENTS.jsonl lines.
If user chooses [4]: surface `/pathly team|debug|explore <FEATURE>` options.
In auto-flow mode, default to [1] Proceed without asking. Still display the menu — just note "auto-flow: proceeding".

### Step 3 — Execute agent instructions

Execute the instructions returned by `{{FSM_NEXT_ACTION}}` for the returned agent.

Track two counters, reset at the start of each stage:
- `needs_context_count = 0`
- `feedback_round_count = 0`

**NEEDS_CONTEXT loop:**
- If the agent outputs NEEDS_CONTEXT:
  1. `needs_context_count += 1`
  2. If `needs_context_count >= limits.needs_context_per_stage`: warn user and halt.
  3. Else: call `scout-path`, feed summary back, resume.
  4. Repeat until agent no longer emits NEEDS_CONTEXT.
- The FSM is NOT notified about NEEDS_CONTEXT cycles — fully internal to the skill.

### Step 4 — Complete the stage

When stage work is complete, call:
`{{FSM_COMPLETE_STAGE}}(flow="team", topic=FEATURE, project_root=PROJECT_ROOT)`

Receives one of:
- `{next_state, agent, instructions, limits}` — advance
- `{done: true}` — pipeline complete
- `{blocked: true, target_agent: "human", file, instructions}` — human must decide
- `{blocked: true, target_agent: <agent>, file, instructions}` — feedback to resolve
- `{decide: true, question, context, options, default}` — Level 3 routing

**Feedback resolution loop:**
- `feedback_round_count += 1`
- If `feedback_round_count >= limits.feedback_rounds_per_stage`: write HUMAN_QUESTIONS.md, halt.
- Else: spawn feedback agent, resolve, call `{{FSM_COMPLETE_STAGE}}(resolved_files=[file])`.
- Python deletes the file. Do NOT delete files manually.
- One file at a time — do NOT batch-resolve before calling.

**Human-blocked:** Surface instructions to user. When user confirms resolution, call
`{{FSM_COMPLETE_STAGE}}(resolved_files=["HUMAN_QUESTIONS.md"])`. Python deletes the file.

Display contextual menu after every call to `{{FSM_COMPLETE_STAGE}}` before executing the next agent.

### Step 5 — Repeat

Repeat Steps 2–4 until `done=true`.

## Nano mode

If `mode = nano`, run inline — do not route to sub-skills.

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

**Step 3 — Scope check:** Run `git diff --name-only HEAD`. Count changed files (exclude `plans/`).
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
