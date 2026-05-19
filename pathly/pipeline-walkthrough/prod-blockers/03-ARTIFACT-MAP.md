# prod-blockers — Artifact Map

**Date:** 2026-05-19

---

## Source Files Changed

| File | Change |
|------|--------|
| `src/pathly_orchestrator/http_server.py` | Conv 1 (traceback strip, logging.exception) + Conv 3 (path-traversal guard, tailer cleanup) |
| `src/pathly_orchestrator/fsm.py` | Conv 1 (datetime.now(timezone.utc), timeout=30 on subprocess) |
| `src/install_cli/materialize.py` | Conv 2 (manifest integrity: _manifest_version, _manifest_hash, confirm_manifest uninstall guard) |
| `tests/test_rollback.py` | Conv 4 — new file (S4.1 rollback test) |
| `tests/test_manifests.py` | Conv 4 — new file (S4.2 parametrized manifest field test) |
| `tests/test_fsm.py` | Testing fix — added timeout=30 to expected call assertions |
| `tests/test_setup.py` | Testing fix — updated _write_manifest helper to produce v1 manifest with hash |

---

## Feedback Artifacts

| File | Cycle | Outcome |
|------|-------|---------|
| `feedback/REVIEW_FAILURES.md` | Review round 1 | Resolved — 3 violations fixed |
| `feedback/TEST_FAILURES.md` | Test round 1 | Resolved — S2.1 uninstall confirm_manifest restored |
| `feedback/TEST_FAILURES.md` | Test round 2 | Resolved — test_fsm.py + test_setup.py fixtures updated |

---

## Plan Files

All 9 plan files in `pathly/plans/prod-blockers/`:
`FEATURE_INDEX.md`, `USER_STORIES.md`, `IMPLEMENTATION_PLAN.md`, `PROGRESS.md`, `CONVERSATION_PROMPTS.md`, `ARCHITECTURE_PROPOSAL.md`, `EDGE_CASES.md`, `HAPPY_FLOW.md`, `FLOW_DIAGRAM.md`
