# FEATURE_INDEX.md — studio-backend

## Overview

Python-only backend foundation for the new Pathly Studio design. Centralizes SQLite from
per-feature DBs to one `~/.pathly/pathly.db`, expands schema from 3 to 12 tables, seeds
static catalog data from `src/pathly_data/`, updates all callers, adds a services/ layer,
and registers all `/api/*` routes in `http_server.py`.

**Rigor:** standard
**Conversation cap:** 4 (hard limit)

---

## Plan Files

| File | Purpose |
|---|---|
| FEATURE_INDEX.md | This file — orientation and path verification |
| USER_STORIES.md | Acceptance criteria for all deliverables |
| IMPLEMENTATION_PLAN.md | Phase-by-phase build plan with done-when checks |
| PROGRESS.md | Conversation status (TODO / DONE) |
| CONVERSATION_PROMPTS.md | Verbatim builder prompts for each conversation |
| HAPPY_FLOW.md | End-to-end narrative — first-time Studio user |
| EDGE_CASES.md | Out-of-band conditions and how to handle them |
| ARCHITECTURE_PROPOSAL.md | Why centralized DB + services layer was chosen |
| FLOW_DIAGRAM.md | ASCII data-flow from runner start to API query |

---

## Codebase Touchpoints

**Verify these paths exist before editing. Glob each one.**

| File | Conv | Change type |
|---|---|---|
| `src/pathly_orchestrator/db.py` | 1, 2 | REWRITE (Conv 1 — signatures + schema load); ADD `from .seed import seed_if_empty` call (Conv 2) |
| `src/pathly_orchestrator/seed.py` | 2 | CREATE — seed_if_empty() reads pathly_data/, calls db helpers |
| `src/pathly_orchestrator/eventlog.py` | 2 | MODIFY — derive project_root from storage_path; update 4 get_db call sites (highest-risk caller) |
| `src/pathly_orchestrator/supervisor.py` | 2 | MODIFY — update 4 get_db call sites; rewrite recover_stale_mirrors discovery (glob → DB query) |
| `src/pathly_orchestrator/fsm_ops.py` | 2 | LIKELY UNTOUCHED — calls go indirect via eventlog; only touch if eventlog fix is insufficient |
| `src/pathly_orchestrator/otel_export.py` | 2 | MODIFY — 2 lines: get_db() no args, read_events adds project_root |
| `src/pathly_orchestrator/http_server.py` | 4 | MODIFY — 1 line only: `app.register_blueprint(api_bp)` |
| `src/pathly_orchestrator/api/__init__.py` | 4 | CREATE — Flask Blueprint with all /api/* routes |
| `src/pathly_orchestrator/services/__init__.py` | 3 | CREATE |
| `src/pathly_orchestrator/services/flow_service.py` | 3 | CREATE |
| `src/pathly_orchestrator/services/telemetry_service.py` | 3 | CREATE — events + spans |
| `src/pathly_orchestrator/services/config_service.py` | 3 | CREATE — agents, skills, overrides |
| `src/pathly_orchestrator/services/artifact_service.py` | 3 | CREATE |
| `tests/test_services.py` | 3 | CREATE |
| `src/pathly_data/core/flows/*.flow.yaml` | 2 | READ — seed source |
| `src/pathly_data/core/agents/**/*.md` | 2 | READ — seed source |
| `src/pathly_data/core/skills/**/*.md` | 2 | READ — seed source |
| `src/pathly_data/adapters/claude/_meta/*.yaml` | 2 | READ — seed metadata source |

---

## Conversation Map

| Conv | Title | Phases | Stories | Status |
|---|---|---|---|---|
| Conv 1 | db.py rewrite | Phase 0 (pre-flight) + Phase 1 (db rewrite) | S1.1, S1.2 | TODO |
| Conv 2 | Seed data + Caller updates | Phase 2 (seed) + Phase 3 (callers) | S1.3, S2.1 | TODO |
| Conv 3 | Services layer | Phase 4 (services + tests) | S3.1 | TODO |
| Conv 4 | HTTP routes | Phase 5 (routes) | S4.1, S4.2 | TODO |

---

## Key Source Paths (verify these exist)

```
src/pathly_orchestrator/db.py
src/pathly_orchestrator/eventlog.py
src/pathly_orchestrator/supervisor.py
src/pathly_orchestrator/fsm_ops.py
src/pathly_orchestrator/otel_export.py
src/pathly_orchestrator/http_server.py
src/pathly_data/core/flows/
src/pathly_data/core/agents/
src/pathly_data/core/skills/
src/pathly_data/adapters/claude/_meta/
tests/
```
