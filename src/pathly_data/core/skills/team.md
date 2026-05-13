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

## Feature detection

If no `FEATURE` was found in `$ARGUMENTS`, auto-detect:
1. Read `plans/*/STATE.json` files, sorted by modification time (newest first).
   Use the most recent feature whose state is not `IDLE` or `DONE`.
2. If none found, use the most recently modified `plans/*/` folder (excluding `.archive/`).
3. If multiple candidates exist: list them numbered and ask "Which feature? [1/2/…]"
4. If no `plans/` folder exists or is empty: stop →
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

## Spawn orchestrator

After mode selection is complete (autoFlow is set), spawn the **orchestrator** agent with:
- FEATURE: [parsed feature name]
- rigor: [parsed rigor]
- autoFlow: [true/false]
- entryStage: [parsed entryStage, default: discovery]

The orchestrator handles all FSM state recovery, routing, git commits, PROGRESS.md updates,
and artifact archiving. Do not perform these actions in team.md.

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
