# PROGRESS.md — studio-backend

**Feature:** studio-backend
**Status:** IN PROGRESS

---

## Conversation Status

| Conv | Title | Stories | Status |
|---|---|---|---|
| Conv 1 | db.py rewrite | S1.1, S1.2 | DONE |
| Conv 2 | Seed data + Caller updates | S1.3, S2.1 | TODO |
| Conv 3 | Services layer | S3.1 | TODO |
| Conv 4 | HTTP routes | S4.1, S4.2 | TODO |

---

## Phase Status

| Phase | Title | Conv | Status |
|---|---|---|---|
| Phase 0 | Pre-flight | Conv 1 | DONE |
| Phase 1 | db.py rewrite | Conv 1 | DONE |
| Phase 2 | Seed data | Conv 2 | TODO |
| Phase 3 | Caller updates | Conv 2 | TODO |
| Phase 4 | Services layer | Conv 3 | TODO |
| Phase 5 | HTTP routes | Conv 4 | TODO |

---

## Notes

- Conv 1 must complete Phase 0 (pre-flight record) before beginning Phase 1 edits.
- Conv 2 depends on Phase 1 helpers being stable — do not start Conv 2 before Conv 1 VERIFY.md shows RESULT: PASS.
- Conv 3 depends on seed data being present for catalog tests.
- Conv 4 depends on services/ layer being importable.
