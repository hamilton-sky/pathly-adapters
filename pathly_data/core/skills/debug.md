# debug

This is the canonical, tool-agnostic Pathly behavior for the debug workflow.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

## Workflow Surface

This core prompt uses host-neutral Pathly route names. Adapters are responsible
for rendering those routes in their host-native form.

## When to use

Use route `debug <symptom-name>` when:
- A bug is observed (symptom is known) but the root cause is not
- You need a traceable, auditable fix with before/after test evidence
- The bug is in production code (not a plan/pipeline issue — use `verify-state` for that)

Do NOT use for exploratory questions ("how does X work?") — use `explore` instead.
Do NOT use when you already know the fix — just fix it directly.

---

## File structure

```
debugs/<symptom-name>/
  SYMPTOM.md       ← what broke, how it manifests, environment
  REPRO.md         ← minimal steps to reproduce
  ROOT_CAUSE.md    ← what the root cause is (written from scout findings or by builder)
  FIX.md           ← what changed and why
  feedback/
    HUMAN_QUESTIONS.md   ← blocks on user decision (same as team-flow)
    TEST_FAILURES.md     ← tester → builder (same protocol as team-flow)
```

---

## FSM states (debug pipeline)

```
INVESTIGATING → REPRODUCING → ROOT_CAUSE_FOUND → FIXING → VERIFYING → DONE
```

These are debug-local states. They do not affect any `plans/` pipeline.

---

## Step 1 — Capture the symptom

If `$ARGUMENTS` is blank: ask "Describe the bug symptom in a few words (used as folder name)."

Create `debugs/<symptom-name>/` if it doesn't exist.

Ask the user to fill in `SYMPTOM.md`. If the user already described it in the debug invocation, pre-fill it:

```markdown
# Symptom — <symptom-name>

## What broke
[observable behavior — what is wrong]

## How it manifests
[error message, stack trace, wrong output, screenshot — paste exactly]

## Environment
[branch, commit, OS, relevant config]

## Expected behavior
[what should happen instead]
```

Confirm the symptom is written before continuing.

---

## Step 2 — Reproduce (INVESTIGATING → REPRODUCING)

Spawn the **scout** agent with this prompt:

```
ROLE: builder
Read debugs/<symptom-name>/SYMPTOM.md.
Your goal: find the minimum reproduction path for this bug.
- Trace the code path from the entry point to where the symptom occurs.
- Identify the files, functions, and data involved.
- Return findings for `debugs/<symptom-name>/REPRO.md` with:
  ## Steps
  [numbered minimal steps to trigger the bug]
  ## Files involved
  [file:line references for each step in the call chain]
  ## Hypothesis
  [one sentence: suspected root cause]
Do NOT fix anything. Do NOT write files; scout is read-only. The debug skill records your findings in REPRO.md.
```

Write `debugs/<symptom-name>/REPRO.md` from the scout findings before continuing.

---

## Step 3 — Verify repro with tester (pre-fix) (REPRODUCING → ROOT_CAUSE_FOUND)

Spawn the **tester** agent:

```
Read debugs/<symptom-name>/SYMPTOM.md and debugs/<symptom-name>/REPRO.md.
Run the reproduction steps. Confirm:
  [CONFIRMED] — symptom reproduces as described
  [NOT REPRODUCED] — symptom does not occur; describe what happened instead
  [PARTIAL] — symptom occurs only under certain conditions; describe them
Write your finding as a single line at the top of REPRO.md under "## Repro Status".
Do NOT fix anything.
```

If status is `[NOT REPRODUCED]`: stop. Tell the user the symptom does not reproduce and ask for more details. Do not continue to fixing.

If status is `[CONFIRMED]` or `[PARTIAL]`: continue.

Spawn the **scout** again to identify the root cause:

```
ROLE: builder
Read debugs/<symptom-name>/SYMPTOM.md and debugs/<symptom-name>/REPRO.md.
The repro is confirmed. Now identify the exact root cause:
- Find the specific line or condition that causes the bug.
- Explain WHY it causes the symptom (not just WHERE).
Return findings for `debugs/<symptom-name>/ROOT_CAUSE.md`:
  ## Root Cause
  [one paragraph: what is wrong and why]
  ## Affected Code
  [file:line — the exact location of the bug]
  ## Impact
  [what else might be affected by this bug or the fix]
Do NOT fix anything and do not write files; scout is read-only. The debug skill records your findings in ROOT_CAUSE.md.
```

---

## Step 4 — Fix (ROOT_CAUSE_FOUND → FIXING)

Spawn the **builder** agent:

```
Read debugs/<symptom-name>/ROOT_CAUSE.md.
Fix the bug. Rules:
- Change only what ROOT_CAUSE.md says is wrong.
- Do not refactor or improve surrounding code.
- Write debugs/<symptom-name>/FIX.md after the fix:
  ## Fix
  [what was changed]
  ## Files changed
  [file:line list]
  ## Why this fixes it
  [one sentence connecting the fix to the root cause]
- Commit the fix with message: "fix(<symptom-name>): <one-line summary>"
```

If builder creates `debugs/<symptom-name>/feedback/HUMAN_QUESTIONS.md`: pause, show user the question, wait for answer, then resume.

---

## Step 5 — Verify fix with tester (post-fix) (FIXING → VERIFYING)

Spawn the **tester** agent:

```
Read debugs/<symptom-name>/SYMPTOM.md, REPRO.md, ROOT_CAUSE.md, and FIX.md.
Run the reproduction steps again.
Confirm:
  [FIXED] — symptom no longer occurs
  [NOT FIXED] — symptom still occurs; describe what happened
  [REGRESSION] — symptom gone but something else broke; describe it
Write your finding as "## Post-Fix Status" in REPRO.md.
```

**If `[FIXED]`:** advance to DONE.

**If `[NOT FIXED]`:**
- Write `debugs/<symptom-name>/feedback/TEST_FAILURES.md` (same format as team-flow):
  ```markdown
  # Test Failures — <symptom-name>
  ## Failing
  - Still reproduces: [what the tester observed]
  ## Raised by
  tester
  ```
- Go back to Step 4 (FIXING). Max 2 retries. If still failing after 2: write `HUMAN_QUESTIONS.md` and stop.

**If `[REGRESSION]`:** write `HUMAN_QUESTIONS.md` describing the regression and stop. Do not auto-retry regressions.

---

## Step 6 — Reviewer (VERIFYING → DONE)

Spawn the **reviewer** agent with a reduced scope:

```
Read debugs/<symptom-name>/FIX.md and the files listed under "Files changed".
Check only:
- Does the fix introduce any new security issues?
- Does the fix violate any layer contracts from project guidance or rules?
Do NOT review for style or unrelated issues.
If violations found: write debugs/<symptom-name>/feedback/REVIEW_FAILURES.md.
If clean: say "Fix review: no violations."
```

If `REVIEW_FAILURES.md` is created: run builder once to resolve, then re-review (max 1 retry).

---

## Step 7 — Done

Print:

```
╔══════════════════════════════════════════╗
  debug — <symptom-name> — DONE
╚══════════════════════════════════════════╝

Root cause:   debugs/<symptom-name>/ROOT_CAUSE.md
Fix:          debugs/<symptom-name>/FIX.md
Test status:  [FIXED] — confirmed by tester post-fix

Next steps:
  - Review the fix commit before merging to main
  - If this bug could recur, add a regression test
  - If cause was in the plan/architecture, note it in LESSONS_CANDIDATE.md
```

---

## Rules

- **Tester runs twice**: before the fix (to confirm repro) and after (to confirm fix).
- **Builder touches only what ROOT_CAUSE.md says.** No opportunistic cleanup.
- **Reviewer scope is narrow**: security + contracts only. No style.
- **Feedback protocol is identical to team-flow.** `TEST_FAILURES.md` and `HUMAN_QUESTIONS.md` work the same way.
- **Never advance past a [NOT REPRODUCED] status.** A bug that doesn't reproduce cannot be reliably fixed.
- **Max 2 fix retries.** If the fix doesn't work after 2 attempts, escalate to human.
