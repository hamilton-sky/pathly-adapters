# Retrospective — event-phase-summary

## What went well?

- **End-to-end user experience delivered**: All 4 conversations completed within standard rigor. Backend (HTTP endpoint + DB persistence), supervisor integration, frontend rendering, and skill documentation were delivered without scope creep.
- **Clean separation of concerns**: Each layer was isolated enough that reviewers could validate stages independently.
- **Robust error handling**: Optional fields (`phase`, `conv`), missing `text`, and supervisor failures all handled gracefully without brittle integrations.
- **Testing caught incomplete scope**: Tester verified all 6 user stories and found the missing `conv` field in the curl example before RETRO — prevented a documentation gap from shipping.
- **Event replay pattern inherited for free**: PHASE_SUMMARY events automatically survive SSE reconnection via the existing SQLite catch-up mechanism — no new infrastructure needed.

## What could be improved?

- **FSM DB state inconsistency blocked the pipeline**: Wrong state name ("BUILD" instead of "BUILDING") and split-brain DB rows (forward-slash vs backslash project_root on Windows) required multiple manual DB fixes. Root cause: `write_state` (fsm/engine.py) only writes STATE.json while `update_progress` (eventlog) only writes the DB — the FSM always reads from DB, so STATE.json advances were invisible.
- **Scope gate fired due to stale path in CONVERSATION_PROMPTS.md**: The file referenced `pathly-build.md` instead of `development/build.md`, halting a conversation mid-pipeline.
- **No automated test coverage for the new endpoint**: Stories 1–3 validation relied on curl + manual DB queries. The 400-error scenarios lack pytest tests.

## What should we do differently next time?

- **Pre-flight DB consistency check**: Before starting a multi-stage pipeline, validate that STATE.json and the FSM DB reflect the same state and the same normalized project_root.
- **Normalize Windows paths at write time**: Canonicalize `project_root` to forward-slash at all DB write sites to eliminate split-brain rows on Windows.
- **Validate CONVERSATION_PROMPTS.md file paths in CI**: Lint rule that checks all referenced file paths exist, catching the `development/build.md` mismatch before runtime.
- **Add integration tests for `/record_phase_summary`**: Parametrized pytest tests covering all 400 scenarios, event insertion, and SSE replay — remove reliance on manual curl validation.
