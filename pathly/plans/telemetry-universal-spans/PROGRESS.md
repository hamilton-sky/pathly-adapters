# Progress — Telemetry Universal Spans

Status: **BUILT** (pending full-suite confirmation + commit)

| # | Task | State | Notes |
|---|------|-------|-------|
| T1 | `project_agent_done(adapter=…)` + adapter in otel attrs | DONE | `runner/telemetry.py` |
| T2 | `POST /db/invocation` endpoint | DONE | `ops/db_api_invocation.py`; wraps projector, mints trace, never 5xx |
| T3 | Register endpoint | DONE | `ops/db_api.py` (`from . import db_api_invocation as _di`) |
| T4 | `SpawnOpts.jsonResult` → `claude --output-format json` | DONE | `services/cliEngine.ts` |
| T5 | `buildCliArgv` requests json | DONE | `EditorHeader/editorCli.ts` |
| T6 | `terminal.ts` universal projector | DONE | parse json, normalize tail, POST `/db/invocation`; rename runner `meta`→`runnerMeta` |
| T7 | `terminal:spawn` meta arg (preload + types) | DONE | `preload/index.ts`, `types/global.d.ts` |
| T8 | Consumers pass project-tier meta | DONE | aiRouter, split, analyze, comment, editor, diagram(WIP) |
| T9 | Tests | DONE | py T6 (5 passed); `aiRouter.test.ts` updated + completed `openTab` mock |

## Verification

- Python telemetry tests: **5 passed** (`tests/test_telemetry_three_tier.py`).
- Studio typecheck: node **clean**; web **clean** (pre-existing `mermaid` errors are md-diagram WIP, unrelated).
- Studio vitest: **35 passed** (full suite).
- Full Python suite: see commit (running).

## Coverage after this feature

| Spawn | Tier | Telemetry |
|-------|------|-----------|
| FSM / team | feature | ✅ api_lifecycle |
| board single / loop | feature | ✅ supervisor projector |
| editor AI split / analyze / comment / editor | project | ✅ NEW (cost+tokens via json) |
| HQ-chat / AI-router summary | project | ✅ NEW (cost+tokens via json) |
| editor diagram (md-diagram WIP) | project | ✅ NEW (rides untracked file) |
| codex one-shots | project | ⚠️ span-only (no cost parse) |
