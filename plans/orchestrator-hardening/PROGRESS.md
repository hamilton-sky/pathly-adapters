# orchestrator-hardening — Progress

## Status: IN PROGRESS

## Story Status

| Story | Title | Delivered by | Status |
|-------|-------|--------------|--------|
| S1 | Orchestrator + hooks ship as packages | Conv 1 | DONE |
| S2 | STATE.json schema + transition table | Conv 2 | TODO |
| S3 | EVENTS.jsonl concurrency safety | Conv 2 | TODO |
| S4 | Console scripts in README/CHANGELOG | Conv 1 | DONE |
| S5 | Classify hook keyword fix | Conv 3 | TODO |
| S6 | protocol_contract version field | Conv 3 | TODO |
| S7 | Hook parity gap documented + deployment | Conv 4+5 | TODO |
| S8 | Per-stage iteration counter | Conv 4 | TODO |
| S9 | Hooks deployed to Codex + Copilot VS Code | Conv 5 | TODO |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|------|--------|---------|--------|--------|
| 1 | 1.1, 1.2, 1.3, 1.4 | S1, S4 | DONE | `pytest tests/test_hooks.py && pip install -e . && pathly-events summary nonexistent` |
| 2 | 2.1, 2.2, 2.3 | S2, S3 | TODO | `pytest tests/test_orchestrator.py` |
| 3 | 3.1, 3.2 | S5, S6 | TODO | `pytest tests/test_hooks.py tests/test_feedback_protocol.py` |
| 4 | 4.1, 4.2 | S7, S8 | TODO | `pytest && python -c "import yaml,json; yaml.safe_load(open('protocol_contract.yaml'))"` |
| 5 | 5.1, 5.2, 5.3 | S9, S7 | TODO | `pytest tests/test_materialize_hooks.py && pathly-setup codex --dry-run && pathly-setup copilot --dry-run` |

See **CONVERSATION_PROMPTS.md** for exact prompts to paste in each conversation.

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|------|-------|------|-------------|-----------|--------|
| 1 | 1.1 | `src/pathly_orchestrator/` | Move from repo-root `orchestrator/` | Module importable, root path gone | DONE |
| 1 | 1.2 | `src/pathly_hooks/` | Move from repo-root `hooks/` | Module importable, root path gone | DONE |
| 1 | 1.3 | `pyproject.toml` | Add packages + console scripts | `pathly-events summary <feature>` runs | DONE |
| 1 | 1.4 | `README.md`, `CHANGELOG.md` | Document new console scripts | README lists them; CHANGELOG entry written | DONE |
| 2 | 2.1 | `schemas/state.schema.json` | Create JSON Schema with enum + transitions | Existing STATE.json files validate | TODO |
| 2 | 2.2 | `state.py`, `eventlog.py`, `tests/test_orchestrator.py` | Validator in `write_state` + tests | Invalid state and illegal transition raise | TODO |
| 2 | 2.3 | `eventlog.py`, `tests/test_orchestrator.py` | File lock on `append_event` | 10-thread stress test → 500 valid lines | TODO |
| 3 | 3.1 | `classify_feedback.py`, `tests/test_hooks.py` | Drop `"how"` keyword; word-boundary match | "How long…" → [REQ]; design question → [ARCH] | TODO |
| 3 | 3.2 | `protocol_contract.yaml`, `pathly_hooks/__init__.py`, `tests/test_feedback_protocol.py` | Version field + cross-check | Desync fails test loudly | TODO |
| 4 | 4.1 | `docs/SECURITY.md`, `README.md` | Document hook parity (Codex + Copilot VS Code supported; Copilot CLI gap) | SECURITY.md has subsection; README links it | TODO |
| 4 | 4.2 | `schemas/state.schema.json`, `team-flow.md` | Optional `iteration_by_stage` field | Schema accepts both new and old shape | TODO |
| 5 | 5.1 | `materialize.py`, `codex/install.yaml`, `tests/test_materialize_hooks.py` | Deploy hooks to Codex via `~/.codex/hooks.json` | `pathly-setup codex --apply` writes hook file | TODO |
| 5 | 5.2 | `materialize.py`, `copilot/install.yaml`, `tests/test_materialize_hooks.py` | Deploy hooks to Copilot VS Code via `.github/hooks/` | `pathly-setup copilot --apply` writes two hook files | TODO |
| 5 | 5.3 | `docs/SECURITY.md` | Update coverage table to show deployed status | Table reflects deployed state | TODO |

## Prerequisites
- Editable install works: `pip install -e ".[dev]"`
- `pytest` passes on current branch before starting

## Blocked By
- Nothing
