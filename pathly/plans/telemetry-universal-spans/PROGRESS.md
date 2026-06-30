# Progress — Telemetry Universal Spans

Status: **BUILT** (pending full-suite confirmation + commit)

| # | Task | State | Notes |
|---|------|-------|-------|
| T1 | `project_agent_done(adapter=…)` + adapter in otel attrs | DONE | `runner/telemetry.py` |
| T2 | `POST /db/invocation` endpoint | DONE | `ops/db_api_invocation.py`; wraps projector, mints trace, never 5xx |
| T3 | Register endpoint | DONE | `ops/db_api.py` (`from . import db_api_invocation as _di`) |
| T4 | ~~`SpawnOpts.jsonResult` → `--output-format json`~~ | REVERTED | buffered json froze the editor's live progress stream; one-shots stay `--print` (streaming). Cost → stream-json renderer (part 2). |
| T5 | ~~`buildCliArgv` requests json~~ | REVERTED | same — `editorCli.ts` back to plain streaming |
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
| editor AI split / analyze / comment / editor | project | ✅ span (time/tier) — cost via stream-json next |
| HQ-chat / AI-router summary | project | ✅ span (time/tier) — cost via stream-json next |
| editor diagram | project | ✅ span (time/tier) — cost via stream-json next |
| codex one-shots | project | ⚠️ span-only (no result event) |
