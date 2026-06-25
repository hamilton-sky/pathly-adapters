# STORM_SEED — unified-ai-routing

Technical storm (architect lens). Input: `PO_NOTES.md`. Spans Python + Studio layers.

## Core idea

Three single-responsibility pieces, one consumer.

```
            ┌─────────────────────────── selection: {type:'model'|'engine', id} ┐
 caller ──▶ │  ROUTER  │ ──model──▶  AI Model Manager  ──▶ Ollama / GGUF / Brightsky
            └──────────┘ ──engine─▶  CLI Engine        ──▶ terminal.spawn (claude/codex/…)
                  ▲
        board artifacts (auto-summary + per-artifact pick)
```

## Component 1 — CLI Engine (KEEP AS-IS)

- `services/cliEngine.ts` (`buildHeadlessArgv`, `ADAPTER_META`) + `window.pathly.terminal.spawn` + the `terminal.ts` spawn scheduler.
- Already used by Split / Analyze / Evaluate / Send-comment. Runs in the user's Electron env; CLI self-auths. **No change** beyond the Router calling it.

## Component 2 — AI Model Manager (LIFT OUT OF HQ)

- Today the model system is entangled in HQ: `data/models.ts` (catalog), `store/modelStore.ts` (selection), `lib/llmBridge` → `main/ipc/llm.ts` (GGUF + Ollama), `lib/brightskyClient.ts` (Brightsky WS).
- **Extract** an app-level `modelManager` service (renderer) that owns: the catalog (one source of truth), availability, and a single `runModel(id, prompt) → text` entry point that dispatches per transport:
  - Ollama → HTTP `127.0.0.1:11434`
  - GGUF → IPC to main (`llmBridge`)
  - Brightsky → `brightskyClient` WS
- HQ's `ModelSelector` becomes a **consumer** of `modelManager`, not its owner.

## Component 3 — Router (NEW, SMALL)

- `services/aiRouter.ts`: `runJob(job, selection) → Promise<{text, cost_usd?}>`.
  - `selection.type === 'model'` → `modelManager.runModel(id, prompt)`
  - `selection.type === 'engine'` → spawn via CLI Engine (terminal.spawn + buildHeadlessArgv), read result.
- A unified selector UI component lists **models ⊕ CLI engines** in one dropdown (replaces both `SummarySettings` 3-buckets and the `ArtifactsView` localStorage dropdown).

## Consumer — board artifacts (summary)

- "Summarize artifact" = `aiRouter.runJob({kind:'summarize', text:<file>}, selection)` → write result to `comms_artifacts.summary`. No special backend.
- **Two trigger paths:**
  1. **Client-triggered** (drop file / click re-summarize): renderer calls `aiRouter` directly — identical to Split/Analyze.
  2. **Server-triggered** (agent attaches an artifact mid-pipeline): server must NOT run inference. It enqueues a summary request on the board / runner SSE; the connected Studio client picks it up, runs `aiRouter`, posts the result back to `comms_artifacts.summary`. If no client is connected, summary stays filename-only (best-effort) — never run server-side.

## Data model

- Add `summary_selection` (JSON `{type, id}`) to `comms_artifacts`, persisted per artifact.
- App default selection in `app_settings` under a new key (e.g. `ai_routing:default_summary_selection`) — replaces `inference:summary_backend` + `inference:ollama_model`.
- Keep the existing `summary` result column.

## Cleanup (required acceptance criterion)

- DELETE `runner/inference.py` (`minilm`/`ollama`/`haiku`, `summarize_content`, `summarize_async`) and its callers in `runner/hydrate.py` + `blueprints/comms/artifacts.py`.
- DELETE `app_settings` keys/helpers: `get/set_summary_backend`, `get/set_ollama_model`, `inference:*` keys.
- DELETE `Settings/SummarySettings.tsx` + `apiGet/SetSummaryBackend`; remove the `ArtifactsView` localStorage `pathly.comms.uploadSummary` dropdown (replace with unified selector).
- Remove/rewrite tests: `test_inference.py`, `test_summary_backend.py`, `test_comms_artifact_summarize.py`.
- No dead parallel path may remain.

## Risks / decisions

- **Server-triggered + model selection**: models live client-side, so server-triggered summaries depend on a connected client. Accepted: best-effort, client-driven, never server-side inference.
- **Transport reachability**: Python server can reach Ollama HTTP only; GGUF/Brightsky are client-only. The Router enforces "where each job runs."
- **Migration**: existing artifacts keep their `summary`; `summary_selection` defaults to the app default when absent.
- **Concurrency**: engine-selection summaries flow through the existing spawn scheduler caps (no new concurrency path).
- **SOLID**: new TS services ≤150 lines each in their own subfolders; Python changes respect the 400-line cap + layer rules.

## Layers touched → rigor escalator signals

- Cross-layer (Python db/runner/http_server/supervisor + Studio renderer/main) → **ARCHITECTURE_PROPOSAL.md**.
- Multi-component design with a routing diagram → **FLOW_DIAGRAM.md**.
