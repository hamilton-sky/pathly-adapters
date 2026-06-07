# PROGRESS.md — orchestrator-refactor

**Feature:** orchestrator-refactor
**Status:** TODO

---

## Conversation Status

| Conv | Title | Stories | Status |
|---|---|---|---|
| Conv 1 | db/ package | S1.1–S1.4 | DONE |
| Conv 2 | runner/ package | S2.1–S2.4 | DONE |
| Conv 3 | supervisor/ package | S3.1–S3.6 | DONE |
| Conv 4 | http_server/ package | S4.1–S4.6 | DONE |
| Conv 5 | Integration + cleanup | S5.1–S5.3 | DONE |

---

## Phase Status

| Phase | Title | Conv | Status |
|---|---|---|---|
| Phase 1 | db/ decomposition | Conv 1 | DONE |
| Phase 2 | runner/ decomposition | Conv 2 | DONE |
| Phase 3 | supervisor/ decomposition | Conv 3 | TODO |
| Phase 4 | http_server/ decomposition | Conv 4 | TODO |
| Phase 5 | Integration + cleanup | Conv 5 | TODO |

---

## Notes

- Conv 1 (db/) is independent — no other package depends on it changing.
- Conv 2 (runner/) must complete before Conv 3 (supervisor imports runner).
- Conv 3 (supervisor/) must complete before Conv 4 (http_server imports supervisor for SSE globals).
- Conv 4 must be done on a branch — it touches the live HTTP server; test with `pathly-fsm-http` smoke test.
- Conv 5 is a verification pass only — no new code, only cleanup and docs.
