# team-flow

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

Conflict checks (stop and report):
- `strict` + `fast` → `strict mode requires human approval gates; remove fast or choose standard fast.`
- `nano` + `strict|standard|plan|build|test` → `nano mode has no plan stages; remove the conflicting flag or choose lite instead.`

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

---

## FSM operations (filesystem-native)

All state is stored in two files under `plans/<feature>/`:

- **STATE.json** — snapshot: `{"current": "STATE_NAME", "feature": "...", "rigor": "..."}`
- **EVENTS.jsonl** — append-only log: one JSON object per line

**Transition state:** Write STATE.json with the new `current` value.
Append `{"type": "STATE_TRANSITION", "to": "NEW_STATE", "ts": "<iso-timestamp>"}` to EVENTS.jsonl.

**Log an event:** Append a JSON line to EVENTS.jsonl. Common types:
`FILE_CREATED`, `FILE_DELETED`, `HUMAN_RESPONSE`, `RETRY`, `AGENT_DONE`, `NO_DIFF_DETECTED`, `IMPLEMENT_COMPLETE`

---

## State recovery

Recover in this order. Print one log line showing the result.

1. Read `plans/<feature>/STATE.json`. If it parses cleanly → use `current` field as state.
2. If absent/unreadable → replay `plans/<feature>/EVENTS.jsonl` line by line; the last
   `STATE_TRANSITION` event gives the current state.
3. If neither file exists → start from IDLE.
   In `strict` rigor: stop — "STATE.json and EVENTS.jsonl not found — cannot recover state in strict mode."

Log lines:
- `[FSM] State recovered from STATE.json: <state>`
- `[FSM] State reconstructed from EVENTS.jsonl: <state> (N events)`
- `[FSM] No prior state found — starting from IDLE`

**Disk feedback wins:** Scan `plans/<feature>/feedback/`. If any files exist and state is not
already BLOCKED, transition state → BLOCKED_ON_FEEDBACK.
Append `{"type": "FILE_CREATED", "file": "<highest-priority-file>"}` to EVENTS.jsonl.
Print: `[FSM] State corrected by disk feedback: <old> → BLOCKED_ON_FEEDBACK`

## Entry stage override

If `entryStage` was set, apply health checks then override the FSM state before routing:

| entryStage | Health check | Override state |
|---|---|---|
| `plan` | none | PLANNING |
| `build` | plan files exist for rigor; print `[SKIPPED] Discovery + plan → entering at build` | BUILDING |
| `test` | plan files exist + all PROGRESS.md convs DONE; print `[SKIPPED] ... → entering at test` | TESTING |

Health check failures: stop and report the specific missing requirement.

## Routing

Route to the sub-skill matching the current FSM state. Pass `FEATURE [rigor] [autoFlow]` as arguments.
After the sub-skill returns control, re-read `STATE.json` and route again.
Repeat until state is DONE or the user stops the pipeline.

| FSM state | Sub-skill |
|---|---|
| IDLE / PO_DISCUSSING / EXPLORING / STORMING | `team-flow/discover` |
| PLANNING | `team-flow/plan` |
| BUILDING | `team-flow/build` |
| REVIEWING | `team-flow/review` |
| TESTING | `team-flow/test` |
| RETRO | `team-flow/retro` |
| BLOCKED_ON_HUMAN | Print `plans/<feature>/feedback/HUMAN_QUESTIONS.md`. Wait for user. On reply: delete file, append `{"type": "HUMAN_RESPONSE", "value": "<reply>"}` to EVENTS.jsonl, restore prior state in STATE.json, re-route. |
| DONE | Print `[Complete] Feature '[feature]' is DONE.` Stop. |
