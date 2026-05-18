# prod-blockers — Feature Index

> **Read this first.** Every agent working on this feature should load this file before any other plan file.
> It maps every file in this folder so you can fetch only what you need in one read.

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `FEATURE_INDEX.md` | Planner | All agents | This file — single entry point for feature context |
| `USER_STORIES.md` | Planner | Tester, Reviewer | Acceptance criteria — the contract |
| `IMPLEMENTATION_PLAN.md` | Planner | Builder, Architect | Phase-by-phase design — the what and how |
| `CONVERSATION_PROMPTS.md` | Planner | Builder | Exact builder prompts — one section per conversation |
| `PROGRESS.md` | Builder, Orchestrator | Orchestrator, Builder | Conversation status — the checkpoint |

### Optional plan files (present if signals fired)

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | yes | Cross-layer design decisions for SSE hardening and manifest integrity |
| `EDGE_CASES.md` | yes | Failure modes and risk scenarios for each fix |
| `HAPPY_FLOW.md` | yes | Golden-path narrative for a successful install + orchestration cycle |
| `FLOW_DIAGRAM.md` | yes | Multi-component interaction diagram for SSE thread lifecycle |

---

## Codebase touchpoints

Files in the live repo that this feature reads or modifies.

| Codebase file | Conversation | What changes |
|---|---|---|
| `src/pathly_orchestrator/http_server.py` | Conv 1 | Strip traceback from 500 responses; log with `logging.exception()` |
| `src/pathly_orchestrator/fsm.py` | Conv 1 | Replace `datetime.utcnow()` with `datetime.now(timezone.utc)`; add `timeout=30` to both `subprocess.run()` calls; catch `TimeoutExpired` |
| `src/install_cli/materialize.py` | Conv 2 | Add `_manifest_version` + SHA-256 hash to manifest writes; validate on load; abort on missing-file uninstall |
| `src/pathly_orchestrator/http_server.py` | Conv 3 | Resolve and boundary-check `project_root` in `/events/stream`; stop+remove tailer threads when last client disconnects |
| `tests/test_rollback.py` | Conv 4 | New: test that a mid-loop write failure leaves no orphaned files |
| `tests/test_manifests.py` | Conv 4 | New: parametrized test asserting required fields in all 3 manifest JSON files |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | Quick fixes — traceback leak, deprecated datetime, subprocess timeout | S1.1, S1.2, S1.3 | TODO | `http_server.py`, `fsm.py` |
| 2 | Manifest integrity | S2.1 | TODO | `materialize.py` |
| 3 | SSE hardening — path traversal + thread leak | S3.1, S3.2 | TODO | `http_server.py` |
| 4 | Tests — rollback and manifest field validation | S4.1, S4.2 | TODO | `tests/test_rollback.py`, `tests/test_manifests.py` |

---

## Feedback files (transient — deleted after resolution)

Live in `pathly/plans/prod-blockers/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
