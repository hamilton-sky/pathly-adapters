# quick-fix

Fast standalone fix workflow for known issues. No REPRO or ROOT_CAUSE overhead —
use this when you know what is broken and want a scoped, committed fix in three steps.

Use `debug` instead if the root cause is unknown.

## When to use

- You can describe the broken behaviour in one sentence
- You have a file or area in mind (even roughly)
- You do not need a full audit trail — just a clean commit and a `FIX.md`

---

## File structure

```
pathly/fixes/<fix-name>/
  ISSUE.md      ← what is broken and where (written at skill entry)
  FIX.md        ← what changed and why (written by builder)
  feedback/
    TEST_FAILURES.md     ← tester → builder
    HUMAN_QUESTIONS.md   ← blocks on user decision
```

---

## Step 1 — Capture the issue

Parse `$ARGUMENTS`: the first non-keyword word is `FIX_NAME` (used as folder name).

If `$ARGUMENTS` is blank: ask "Describe the issue in a few words (used as folder name)."

Write `pathly/fixes/<FIX_NAME>/ISSUE.md`:

```markdown
# Issue — <fix-name>

## What is broken
[observable wrong behaviour — one or two sentences]

## Affected area
[file path, module name, or component — as specific as possible]

## Expected behaviour
[what should happen instead]
```

Pre-fill from `$ARGUMENTS` if the user described it inline.
Confirm the issue is written before continuing.

---

## Step 2 — Run the FSM

`PROJECT_ROOT` = cwd at skill invocation.

Invoke the `fsm-call` skill with:
```json
{"action":"next_action","flow":"quick-fix","topic":"<FIX_NAME>","project_root":"<PROJECT_ROOT>"}
```

Display the contextual menu (same format as team.md):

```
─────────────────────────────────────────────────────────────────
  Pathly  ·  quick-fix  ·  <FIX_NAME>
  Stage: <state>   Agent: <agent>
─────────────────────────────────────────────────────────────────
  [1] Run    — execute <agent> now
  [2] Skip   — advance without running
  [3] Abort  — exit without changes
─────────────────────────────────────────────────────────────────
  Reply [1–3]:
```

Wait for user reply.

---

## Step 3 — Execute the stage

On **[1] Run**: execute the agent returned by the FSM.

**SCOPING (scout):** spawn `scout` with the prompt:
```
Read ISSUE.md at pathly/fixes/<FIX_NAME>/ISSUE.md.
Locate the code responsible for the described behaviour.
List the files and functions that need to change. Keep it brief — this is a fast fix.
```

**FIXING (builder):** spawn `builder` with the prompt:
```
Read pathly/fixes/<FIX_NAME>/ISSUE.md and the scout findings above.
Apply the minimal correct fix. Do not refactor beyond the fix.
Write pathly/fixes/<FIX_NAME>/FIX.md when done:
  ## What changed
  [files and lines modified]
  ## Why
  [the root cause in one sentence and how the fix addresses it]
```

**VERIFYING (tester):** spawn `tester` with the prompt:
```
Read pathly/fixes/<FIX_NAME>/FIX.md.
Run the relevant tests for the changed files.
If tests fail, write pathly/fixes/<FIX_NAME>/feedback/TEST_FAILURES.md and halt.
If all pass, confirm clean.
```

---

## Step 4 — Complete the stage

After the agent finishes, invoke the `fsm-call` skill with:
```json
{"action":"complete_stage","flow":"quick-fix","topic":"<FIX_NAME>","project_root":"<PROJECT_ROOT>"}
```

Handle the result:

- `blocked` → show blocked panel (same as fix.md Step 5), resolve, loop.
- `decide` → show decision panel, wait for user answer, invoke `complete_stage` with `decision`, handle result.
- `done` → print `Fix complete: <FIX_NAME>` and exit.
- Otherwise → show the new state and agent, return to Step 3.

---

## On **[2] Skip**

Invoke `complete_stage` with `{"skipped":true}`. Handle result as above.

## On **[3] Abort**

Print: "Aborted." and exit.
