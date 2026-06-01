---
name: Progress
---
# Multi-Adapter Runner — Progress

## Status: NOT STARTED

## Story Status

| Story | Title | Delivered by | Status |
|-------|-------|--------------|--------|
| S1 | Adapter→command contract | Conv 1 | TODO |
| S2 | Controllable autonomous supervisor | Conv 2 | TODO |
| S3 | Control API + /events/runner SSE | Conv 3 | TODO |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|------|--------|---------|--------|--------|
| 1 | 0-4 | S1 | TODO | `python -m pytest tests/ -q` + `python scripts/gen_adapters_ts.py` |
| 2 | 5-7 | S2 | TODO | `python -m pytest tests/ -q` |
| 3 | 8-10 | S3 | TODO | `python -m pytest tests/ -q` + curl `/runner/start` and `/events/runner` |

See **CONVERSATION_PROMPTS.md** for exact prompts.

**Dependency:** strict `1 → 2 → 3`. Hard CI gate after Conv 3 (full Python path curl-drivable) before the `hq-panel` feature starts.
**Upstream dependency:** `multi-adapter-routing` Conv 1 (preferred_adapter) must be shipped first.

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|------|-------|------|-------------|-----------|--------|
| 1 | 0 Pre-flight | none | Baseline + confirm preferred_adapter exists | Baseline green, dep confirmed | TODO |
| 1 | 1 adapters.yaml | `src/pathly_data/core/adapters.yaml` | Command map for 3 adapters | File parses, shape correct | TODO |
| 1 | 2 resolve_command | `src/pathly_orchestrator/adapters.py` | Map → {argv, terminal_kind, supports_resume} | Returns correct argv; unknown raises | TODO |
| 1 | 3 gen + staleness | `scripts/gen_adapters_ts.py`, `studio/.../lib/adapters.gen.ts` | Generate TS mirror + test | Generator writes; staleness test passes | TODO |
| 1 | 4 invoke_agent | `src/pathly_orchestrator/runner.py` | Build cmd via resolve_command | claude path unchanged; tests pass | TODO |
| 2 | 5 RunnerState | `src/pathly_orchestrator/supervisor.py` | State + registry + JSON mirror | Registry works; stale→error on startup | TODO |
| 2 | 6 Loop + caps + abort | `src/pathly_orchestrator/supervisor.py` | Threaded loop, boundary caps, hard abort | Caps stop run; abort kills ~2s | TODO |
| 2 | 7 Decision + session | `supervisor.py`, `runner.py` | FSM-fed decision; continue-vs-new | input() replaced; session resolved | TODO |
| 3 | 8 Control endpoints | `src/pathly_orchestrator/http_server.py` | 8 POST + status | Endpoints thin; caps required; 409 | TODO |
| 3 | 9 SSE stream | `src/pathly_orchestrator/http_server.py` | /events/runner + _broadcast_runner | Events stream; existing SSE intact | TODO |
| 3 | 10 Tests | `tests/` | Endpoint + SSE coverage | All pass | TODO |

## Prerequisites
- `multi-adapter-routing` Conv 1 shipped (preferred_adapter).
- `tests/` green at baseline.

## Blocked By
- Upstream: `multi-adapter-routing` Conv 1.
