# Feature Index — orchestrator-refactor

**What:** SOLID refactor of the four largest files in `pathly_orchestrator`.

**Why:** SRP violations make these files hard to navigate, test, and extend:
- `http_server.py` (1,784 lines) — transport + business logic + SSE + runner + FSM mixed together
- `supervisor.py` (1,263 lines) — state machine + process management + user interaction combined
- `runner.py` (659 lines) — argv building + output parsing + event mutation + CLI pipeline
- `db.py` (607 lines) — connection mgmt + migrations + 9 query domains

**How:** Each file becomes a package (`db/`, `runner/`, `supervisor/`, `http_server/`) with a
`__init__.py` that re-exports the original public API unchanged — zero breaking changes for callers.

**Scope:** Pure structural refactor — no new features, no API changes, no logic changes.
Every function moves unchanged; only its file location changes.

**Plan files:**
- [ARCHITECTURE_PROPOSAL.md](ARCHITECTURE_PROPOSAL.md) — target structure + design decisions
- [USER_STORIES.md](USER_STORIES.md) — acceptance criteria per package
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) — 5-conversation breakdown
- [CONVERSATION_PROMPTS.md](CONVERSATION_PROMPTS.md) — exact steps per conversation
- [PROGRESS.md](PROGRESS.md) — conversation status tracking
