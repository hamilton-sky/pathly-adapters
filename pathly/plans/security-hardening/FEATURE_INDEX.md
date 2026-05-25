---
name: Feature Index
---
# security-hardening — Feature Index

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
| `HAPPY_FLOW.md` | Planner | Builder | Golden-path narrative |
| `EDGE_CASES.md` | Planner | Tester | Failure modes and risk scenarios |
| `ARCHITECTURE_PROPOSAL.md` | Planner | Architect, Builder | Cross-layer design decisions |
| `FLOW_DIAGRAM.md` | Planner | Builder | ASCII interaction diagram |

### Optional plan files (present if signals fired)

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | yes | IPC security boundary decisions |
| `EDGE_CASES.md` | yes | Attack vectors + rollback scenarios |
| `HAPPY_FLOW.md` | yes | Normal install + terminal launch paths |
| `FLOW_DIAGRAM.md` | yes | Terminal IPC trust boundary diagram |

---

## Codebase touchpoints

| Codebase file | Conversation | What changes |
|---|---|---|
| `studio/src/main/ipc/terminal.ts` | Conv 1 | Add command allowlist + cwd validation + tabId ownership check |
| `studio/src/main/ipc/fs.ts` | Conv 1 | Verify path safety (read-only check, no changes expected) |
| `src/pathly_telemetry/server.py` | Conv 2 | DELETE — dead MCP implementation, replaced by HTTP endpoint |
| `src/pathly_telemetry/__main__.py` | Conv 2 | DELETE — only caller was the dead server |
| `src/pathly_telemetry/__init__.py` | Conv 2 | Update comment (remove "MCP server") |
| `src/pathly_telemetry/storage.py` | Conv 2 | Add 5 MB rotation cap before append |
| `.gitignore` | Conv 2 | Add `build/lib/` and `build/bdist*/` entries |
| `src/install_cli/materialize.py` | Conv 3 | Catch ValueError on manifest hash mismatch; raise RuntimeError with clear message |
| `src/install_cli/setup_command.py` | Conv 3 | Wrap rollback inner-except to log failures instead of silently swallowing |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | Terminal IPC hardening | S1, S2 | TODO | `terminal.ts` |
| 2 | Dependency + telemetry + git hygiene | S3, S4, S5 | TODO | `pyproject.toml`, `server.py`, `storage.py`, `.gitignore` |
| 3 | Installer error handling | S6 | TODO | `materialize.py`, `setup_command.py` |

---

## Feedback files (transient — deleted after resolution)

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
