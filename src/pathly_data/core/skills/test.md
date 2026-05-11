# test

This is the canonical, tool-agnostic Pathly behavior for the standalone test workflow.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

## Workflow Surface

This core prompt uses host-neutral Pathly route names. Adapters are responsible
for rendering those routes in their host-native form.

## When to use

Use `/test` to verify acceptance criteria for a completed feature, or to run a targeted
test pass against a specific plan folder outside the full team-flow pipeline.

Use `team-flow <feature> test` when running within the full pipeline (build → test → retro).

---

## Feature detection

If `$ARGUMENTS` contains a non-keyword word, use it as `FEATURE`.
Otherwise auto-detect:
1. Read `plans/*/STATE.json` files, sorted by modification time (newest first).
   Use the most recent feature whose state is not `IDLE` or `DONE`.
2. If none found, use the most recently modified `plans/*/` folder (excluding `.archive/`).
3. If multiple candidates exist: list them numbered and ask "Which feature? [1/2/…]"
4. If no `plans/` folder exists or is empty: stop →
   `No active feature found. Start with /pathly go to describe what you want to build.`

## Step 0 — Locate the plan

Parse `$ARGUMENTS` for a plan folder name (FEATURE). If blank, use the auto-detected FEATURE above.

Read `plans/<feature>/PROGRESS.md`. If Status is not COMPLETE (or all conversations
not DONE), stop:

```
Not all conversations are DONE for <feature>. Run /build first.
```

Read `plans/<feature>/USER_STORIES.md` (required). If missing, stop:

```
No USER_STORIES.md found for <feature>. Cannot run acceptance tests without stories.
```

---

## Step 1 — Analyze (tester phase: analyze)

Spawn the **tester** agent with `phase: analyze`:

```
phase: analyze
Read plans/<feature>/USER_STORIES.md.
List what test infrastructure and context you need before verifying — output NEEDS_CONTEXT block only.
```

Parse the `## NEEDS_CONTEXT` block it returns.

---

## Step 2 — Scout (if NEEDS_CONTEXT has entries)

If the block is not `none`, call **scout-flow** with:
- `NEEDS_CONTEXT`: the block from Step 1
- `ROLE: tester`
- `FEATURE: <feature>`

Use the returned compressed summary as `## Test Context`.

If the block is `none`, set Test Context to `none` and skip this step.

---

## Step 3 — Test (tester phase: test)

Spawn the **tester** agent with `phase: test`:

```
phase: test
Read plans/<feature>/USER_STORIES.md.
Run the verify command(s) to check each acceptance criterion.

## Test Context
[compressed summary from Step 2, or "none"]

For each criterion: PASS / FAIL / NOT COVERED.
If any FAIL or NOT COVERED: write plans/<feature>/feedback/TEST_FAILURES.md.
```

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
Read plans/<feature>/feedback/TEST_FAILURES.md.
Fix each failing or uncovered criterion.
Delete plans/<feature>/feedback/TEST_FAILURES.md when resolved.
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
