# prod-blockers — Retrospective

**Feature:** prod-blockers | **Completed:** 2026-05-19 | **Branch:** master

---

## What Was Built

prod-blockers delivered 8 user stories across 4 conversations, fixing 7 production-blocking vulnerabilities and adding test coverage:

- **Conv 1 (HTTP + FSM layer):** S1.1 (stripped tracebacks from `/next_action` and `/complete_stage` 500 responses), S1.2 (replaced `datetime.utcnow()` with `datetime.now(timezone.utc)`), S1.3 (added 30-second timeout to `git add` and `git commit` subprocess calls with `TimeoutExpired` handling).
- **Conv 2 (Install CLI):** S2.1 (added manifest version field and SHA-256 hash validation on write/read; uninstall warns and aborts when manifest entries are missing from disk unless `confirm_manifest=True`).
- **Conv 3 (SSE hardening):** S3.1 (path-traversal guard in `/events/stream` using `.resolve()` boundary checks), S3.2 (tailer thread cleanup — threads stopped and removed from `_tailers` when the last SSE client disconnects).
- **Conv 4 (Test coverage):** S4.1 (rollback test using monkeypatch to verify no orphaned files remain after mid-install failure), S4.2 (parametrized manifest field validation test for 3 plugin/marketplace JSON files).

---

## What Went Well

- All implementations were surgical — no new abstractions introduced; codebase runnable after every conversation.
- No regressions introduced; all 7 pre-existing test failures remained unchanged throughout.
- Clean separation of concerns across layers (HTTP, orchestration FSM, install CLI).

## What Was Rough

- **S2.1 review/tester conflict:** Reviewer required `ValueError` on uninstall guard; USER_STORIES specified warn-and-return. Required a correction cycle.
- **Test regression discovery post-implementation:** `test_fsm.py` and `test_setup.py` broke after S1.3 (timeout=30) and S2.1 (v1 manifest format) because test fixtures were not updated alongside production changes. Caught in testing stage.
- **S4.2 scope:** marketplace.json lacks `author` and `skills` fields; test assertions had to be scoped to plugin-only files for those checks.

---

## Lessons

**Carry forward:**
- Baseline-then-change discipline: recording pre-existing failures upfront prevents false attribution.
- "No new abstractions" constraint keeps scope bounded — worth enforcing in future prod-blocker work.
- Spec acceptance criteria in USER_STORIES (not just the implementation plan) to catch reviewer/tester misalignment before code.

**Do differently:**
- Update test fixtures when changing production behavior — same conversation as the production change, not after-the-fact.
- Validate manifest files as part of schema definition in Conv 2 rather than discovering gaps in Conv 4.
- Brief "spec review" after USER_STORIES is written to verify acceptance criteria align with the implementation plan before building.
