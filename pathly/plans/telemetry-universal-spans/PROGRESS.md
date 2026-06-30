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
| editor AI split / analyze / comment / editor | project | ✅ cost + tokens + tool calls (stream-json) |
| HQ-chat / AI-router summary | project | ✅ cost + tokens + tool calls (stream-json) |
| editor diagram | project | ✅ cost + tokens + tool calls (stream-json) |
| codex one-shots | project | ⚠️ span-only (no result event) |

## Part 2 — stream-json renderer (cost + tokens + tool calls, streaming preserved)

| # | Task | State | Notes |
|---|------|-------|-------|
| T10 | `SpawnOpts.streamJson` → `--output-format stream-json --verbose` | DONE | `cliEngine.ts`; `buildCliArgv` + aiRouter opt in |
| T11 | pure `claudeJson.ts` (parse + stream renderer) + `terminal.ts` wiring | DONE | renders events → clean prose + "⚙ Tool" lines; captures cost/tokens/tool-count; opt-in per tab only |
| T12 | `tool_uses` through `/db/invocation` + `project_agent_done` (otel attr) | DONE | Python |
| T13 | `claudeJson.test.ts` — synthetic stream-json (wrap / multi-chunk / noise) | DONE | 11 tests; the un-live-testable parser is covered |
