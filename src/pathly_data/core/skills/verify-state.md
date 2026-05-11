# verify-state

This is the canonical, tool-agnostic Pathly behavior for the verify-state workflow.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

## Workflow Surface

This core prompt uses host-neutral Pathly route names. Adapters are responsible
for rendering those routes in their host-native form.

Run a consistency check on the feature plan pipeline. If `$ARGUMENTS` is given, check that feature only. If blank, check all features in `plans/`.

---

## Step 1 — Find features to check

If `$ARGUMENTS` is given:
- Check `plans/$ARGUMENTS/` exists. If not: stop → `plans/$ARGUMENTS/ not found.`
- Set `FEATURES = [$ARGUMENTS]`

If no argument:
- List all subdirectories of `plans/` that contain `PROGRESS.md`
- Set `FEATURES = that list`

---

## Step 2 — For each feature, run 3 checks

### Check A — Stale feedback files (with TTL / orphan detection)

```bash
ls plans/$FEATURE/feedback/ 2>/dev/null
```

For each `.md` file found in `plans/$FEATURE/feedback/`:

**A1 — Frontmatter-based checks (preferred, when frontmatter is present):**

Read the YAML frontmatter block at the top of the file (between `---` markers).

If frontmatter is present:
- **Orphan check:** Read `plans/$FEATURE/EVENTS.jsonl`. If `created_by_event` is not
  `"unknown"` and does not appear as any event's `timestamp` or `id` field in the log →
  flag as orphan from a previous run.
  Report as: `[ORPHAN FEEDBACK] plans/$FEATURE/feedback/<file> — event <id> not in current EVENTS.jsonl`
- **TTL check:** Compute `created_at + ttl_hours`. If that time has elapsed (compare to
  current UTC time) →
  flag as stale.
  Report as: `[EXPIRED FEEDBACK] plans/$FEATURE/feedback/<file> — TTL expired at <expiry_time>`

Both orphan and expired files are **safe to delete**. Offer the action to the user:
`Suggestion: delete plans/$FEATURE/feedback/<file> — it is a leftover from a previous run.`

**A2 — Git-based check (fallback, when no frontmatter):**

- Check git log for commits made *after* this file's modification time:
  ```bash
  git log --oneline --since="$(git log -1 --format='%ci' -- plans/$FEATURE/feedback/<file>)" -- . 2>/dev/null | head -5
  ```
- **Flag if:** the feedback file exists AND no commits have been made after it was last modified
- Report as: `[STALE FEEDBACK] plans/$FEATURE/feedback/<file> — open since <date>, no commits since`

---

### Check B — PROGRESS.md DONE items with no matching file coverage

Read `plans/$FEATURE/PROGRESS.md` and `plans/$FEATURE/IMPLEMENTATION_PLAN.md`.

For each conversation marked DONE in `PROGRESS.md`:
- Extract the files that conversation was expected to touch from `IMPLEMENTATION_PLAN.md` (look for file paths listed under that conversation's phase/section)
- Get the full set of files changed on this branch vs. the base branch:
  ```bash
  git diff $(git merge-base HEAD main)...HEAD --name-only -- . ":(exclude)plans/" 2>/dev/null
  ```
- **Flag if:** a conversation is marked DONE but **none** of its expected files appear in the branch diff

If `IMPLEMENTATION_PLAN.md` does not list expected files per conversation, fall back to:
- Count DONE conversations vs. count files changed on branch outside `plans/`
- Flag if DONE count > 0 and changed file count is 0 (nothing was ever committed)

Report as: `[PROGRESS DRIFT] $FEATURE — conversation 'N' marked DONE but none of its expected files appear in branch diff`

---

### Check C — Plan files pointing to deleted code

Read `plans/$FEATURE/IMPLEMENTATION_PLAN.md`. If `plans/$FEATURE/ARCHITECTURE_PROPOSAL.md` exists, read it too. Lite plans may not have ARCHITECTURE_PROPOSAL.md.

Extract all file paths mentioned (e.g. `.py`, `.ts`, `.js`, `src/`, `lib/`):
```bash
grep -oE "[a-zA-Z0-9_.-]+/[a-zA-Z0-9_./-]+" plans/$FEATURE/ARCHITECTURE_PROPOSAL.md plans/$FEATURE/IMPLEMENTATION_PLAN.md 2>/dev/null | grep -v "^plans/" | sort -u
```

For each path found:
- Check if the file exists: does it exist in the working tree?
- **Flag if:** a path is mentioned in the plan but the file does not exist

Report as: `[DEAD REFERENCE] plans/$FEATURE — '<path>' mentioned in plan but not found on disk`

---

### Check D — FSM state file consistency (if STATE.json or EVENTS.jsonl exist)

If `plans/$FEATURE/STATE.json` exists:
- Parse it as JSON. If unparseable: flag `[CORRUPT STATE] plans/$FEATURE/STATE.json — invalid JSON`
- Check `state.current` is one of the 14 valid states:
  `IDLE, STORMING, STORM_PAUSED, PLANNING, PLAN_PAUSED, BUILDING, REVIEWING, IMPLEMENT_PAUSED, TESTING, TEST_PAUSED, RETRO, BLOCKED_ON_FEEDBACK, BLOCKED_ON_HUMAN, DONE`
- If not: flag `[INVALID STATE] plans/$FEATURE/STATE.json — unknown state: <value>`
- Cross-check: if `state.current` is not `BLOCKED_ON_FEEDBACK` or `BLOCKED_ON_HUMAN`, but feedback files exist in `plans/$FEATURE/feedback/` → flag `[STATE DRIFT] STATE.json says <state> but feedback files are open: <files>`

If `plans/$FEATURE/EVENTS.jsonl` exists:
- Verify every line is valid JSON. If any line fails: flag `[CORRUPT EVENTS] plans/$FEATURE/EVENTS.jsonl — invalid JSONL at line N`
- Check the last event's `toState` matches `STATE.json`'s `current` field (if both exist). If not: flag `[EVENTS DRIFT] EVENTS.jsonl last toState=<X> but STATE.json current=<Y>`

If neither file exists and `rigor = strict`: flag `[MISSING FSM FILES] plans/$FEATURE — strict rigor requires STATE.json and EVENTS.jsonl`

---

## Step 3 — Report

Print a structured summary:
```text
╔══════════════════════════════════════════╗
  verify-state — $FEATURE (or: all features)
╚══════════════════════════════════════════╝

✓  No issues        ← if everything clean
⚠  N issue(s) found ← if problems detected

[ORPHAN FEEDBACK]   plans/.../feedback/REVIEW_FAILURES.md — event 2026-04-28T10:00:00Z not in current EVENTS.jsonl → safe to delete
[EXPIRED FEEDBACK]  plans/.../feedback/ARCH_FEEDBACK.md — TTL expired at 2026-04-29T10:00:00Z → safe to delete
[STALE FEEDBACK]    plans/.../feedback/REVIEW_FAILURES.md — open since 2026-04-28, no commits since
[PROGRESS DRIFT]    hotel-search — 3 conversations DONE but only 1 implementation commit found
[DEAD REFERENCE]    nl-workflow-compiler — 'src/engine/pathly planner/nl_compiler.py' mentioned but not found
[INVALID STATE]     hotel-search — STATE.json has unknown state: BLOCKED
[STATE DRIFT]       hotel-search — STATE.json says BUILDING but REVIEW_FAILURES.md is open
[CORRUPT EVENTS]    hotel-search — EVENTS.jsonl invalid JSONL at line 7
```

If all clear: `All checks passed. Pipeline state looks consistent.`

If issues found: list each one. Do NOT auto-fix. Report only.

---

## Rules

- **Read-only:** Never edit files, never delete feedback files.
- **Objective:** Do not make assumptions about correctness — report what the data shows.
- **Robustness:** If a check cannot run (git not available, file unreadable), report that check as SKIPPED, not PASS.
- **Context:** Dead references in `CONVERSATION_PROMPTS.md` are common and expected (future work) — only flag `IMPLEMENTATION_PLAN.md` and `ARCHITECTURE_PROPOSAL.md` when present.
