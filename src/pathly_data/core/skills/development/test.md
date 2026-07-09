# test

This is the canonical, tool-agnostic Pathly behavior for the standalone test workflow.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

> Shared protocols — **Scout choreography** and **Live progress logging** — are composed in
> below from fragments. This body covers only the standalone test-workflow specifics.

## Workflow Surface

This core prompt uses host-neutral Pathly route names. Adapters are responsible
for rendering those routes in their host-native form.

## When to use

Use `/test` to verify acceptance criteria for a completed feature, or to run a targeted
test pass against a specific plan folder outside the full team pipeline.

Use `team <feature> test` when running within the full pipeline (build → test → retro).

---

## Feature detection

If `$ARGUMENTS` contains a non-keyword word, use it as `FEATURE`.
Otherwise auto-detect:
1. Read `pathly/features/*/STATE.json` files, sorted by modification time (newest first).
   Use the most recent feature whose state is not `IDLE` or `DONE`.
2. If none found, use the most recently modified `pathly/features/*/` folder (excluding `.archive/`).
3. If multiple candidates exist: list them numbered and ask "Which feature? [1/2/…]"
4. If no `pathly/features/` folder exists or is empty: stop →
   `No active feature found. Start with /pathly go to describe what you want to build.`

## Step 0 — Locate the plan

Parse `$ARGUMENTS` for a plan folder name (FEATURE). If blank, use the auto-detected FEATURE above.

Check the build is complete before testing. Query the board task DAG:
```
curl -s "http://127.0.0.1:8765/comms/tasks?feature=<feature>&scope=<feature>"
```
If any task's `task_status` is not `done`, stop:

```
Not all tasks are done for <feature>. Run /build first.
```

If the board is unreachable (older / offline plans), skip the completeness check and proceed on the
plan + repo state.

Read `pathly/features/<feature>/USER_STORIES.md` (required). If missing, stop:

```
No USER_STORIES.md found for <feature>. Cannot run acceptance tests without stories.
```

---

## Step 1 — Analyze (tester phase: analyze)

log-phase PHASE_START analyze

Spawn the **tester** agent with `phase: analyze`:

```
phase: analyze
Read pathly/features/<feature>/USER_STORIES.md.
List what test infrastructure and context you need before verifying — output NEEDS_CONTEXT block only.
```

Parse the `## NEEDS_CONTEXT` block it returns.

log-phase PHASE_DONE analyze

---

## Step 2 — Scout (if NEEDS_CONTEXT has entries)

log-phase PHASE_START scout

Run the Scout choreography with `ROLE: tester`. Use the returned compressed summary as
`## Test Context` (set it to `none` and skip this step if `NEEDS_CONTEXT` was `none`).

log-phase PHASE_DONE scout (include scouts_count = number of entries spawned, or 0 if skipped)

---

## Step 3 — Test (tester phase: test)

log-phase PHASE_START test

Spawn the **tester** agent with `phase: test`:

```
phase: test
Read pathly/features/<feature>/USER_STORIES.md.
Run the verify command(s) to check each acceptance criterion.

## Test Context
[compressed summary from Step 2, or "none"]

For each criterion: PASS / FAIL / NOT COVERED.
If any FAIL or NOT COVERED: write pathly/features/<feature>/feedback/TEST_FAILURES.md.
```

log-phase PHASE_DONE test

---

## Step 4 — Fix loop (if TEST_FAILURES.md exists)

Track `retryCount = 0`.

**If `TEST_FAILURES.md` exists:**

Increment `retryCount`. If `retryCount > 2`: stop —
```
Test failures unresolved after 2 fix cycles. Manual intervention required.
```

Spawn **builder**:
```
Read pathly/features/<feature>/feedback/TEST_FAILURES.md.
Fix each failing or uncovered criterion.
Delete pathly/features/<feature>/feedback/TEST_FAILURES.md when resolved.
```

After builder completes: re-run Step 3.

**If no `TEST_FAILURES.md`:** all criteria pass — proceed to Step 5.

---

## Step 5 — Report

Print the tester's full test plan output showing PASS/FAIL/NOT COVERED per criterion.

Then ask:

```
Test run complete. What next?

[1] Proceed to retro       /retro <feature>
[2] Re-run tests           /test <feature>
[3] Done — keep as record
```

---

## Rules

- **Tester + builder only** — no reviewer, no planner.
- **Tester does not fix code.** Builder handles all fixes.
- **Run before reporting.** Never claim PASS without executing the verify command.
- **Strict rigor:** all NOT COVERED criteria must be resolved before proceeding to retro.
