---
name: Retro
---
# fsm-sqlite — Retrospective

_Date: 2026-06-04 | Conversations: 4 | Rigor: standard_

---

## What went well

- **Clean incremental migration**: Breaking the work into four conversations (db.py → eventlog.py → supervisor → http_server + migration CLI) meant each layer was testable in isolation before the next layer depended on it. No integration surprises.
- **Backward-compat fallbacks**: The "check db path exists, fall back to .jsonl/.json" pattern let the tests cover both legacy and SQLite paths without forking test files.
- **Write lock serialisation**: WAL mode + per-connection write lock was the right design — no deadlocks, no explicit row-level locking needed.
- **Reviewer caught real issues**: Both REVIEW_FAILURES.md cycles identified genuine bugs (BEGIN IMMEDIATE conflict with implicit tx management, migration non-idempotency) before they reached production.
- **Fast test suite**: 428 tests ran in under 100s, giving rapid feedback throughout.

---

## What could be improved

- **Builder conv4 AGENT_DONE missing**: The builder for Conv 4 ran across session boundaries and its AGENT_DONE event was never written to EVENTS.jsonl. Walked out of the pipeline with no cost/token record for that conversation.
- **Pyright `*_args`/`**_kwargs` trap**: Multiple cycles were spent discovering that Pyright warns on `*_args`/`**_kwargs` (underscore-prefixed non-single-underscore names) but not on `*args`/`**kwargs` or `*_`. This cost ~3 edit-diagnose cycles.
- **Scope gate false positives**: Conv 2 triggered two GATE_FAILED scope_gate events for test file updates that were clearly in-scope. Manual override added friction.
- **updated_at NULL in runner_state**: The reviewer flagged this as a non-blocking warning but it should be resolved — the watcher reads this field for staleness detection.

---

## What to do differently next time

- **Pre-warm Pyright patterns**: When writing test stubs that mock functions taking mixed positional/keyword args, default to `*args, **kwargs` (not `*_args`/`**_kwargs`) to avoid the Pyright unused-var warning loop.
- **Session boundary AGENT_DONE**: When a build conversation spans multiple Claude sessions, write the AGENT_DONE manually before closing the last session. The pipeline EVENTS.jsonl is the record of truth.
- **Migration idempotency as a first-class spec**: Any migration script story should include "idempotent across multiple runs" as an explicit acceptance criterion, not just an architectural note in CONVERSATION_PROMPTS.md.

---

## Key metrics

| Metric | Value |
|---|---|
| Conversations | 4 |
| Total agent spawns | 8 |
| Total tokens | ~604k |
| Total cost | ~$3.26 |
| Test suite | 428 passed, 3 skipped |
| Feedback loops | 2 (conv1 + conv4) |
