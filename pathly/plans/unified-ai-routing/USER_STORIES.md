# User Stories — unified-ai-routing

## US-1 — AI Model Manager (lift out of HQ)
**As** a developer, **I want** the model catalog + transports owned by one app-level
service, **so that** HQ and the board both draw from the same source.
**Acceptance:**
- A `modelManager` service exposes the catalog + `runModel(id, prompt) → {text, cost_usd?}`,
  dispatching Ollama (HTTP) / GGUF (main IPC) / Brightsky (WS).
- HQ `ModelSelector` consumes `modelManager`; HQ chat behavior is unchanged.
- No duplicate catalog remains in HQ.
*Delivered by:* Conversation 1.

## US-2 — Router (model ⊕ engine)
**As** a feature consumer, **I want** one Router that dispatches a job to either a model
or a CLI engine based on a selection, **so that** every AI action uses one primitive.
**Acceptance:**
- `aiRouter.runJob(job, selection)` routes `model` → `modelManager`, `engine` → CLI Engine spawn.
- A unified selector lists models ⊕ CLI engines in one control.
- No Anthropic API-key path anywhere.
*Delivered by:* Conversation 2.

## US-3 — Board artifact summary via Router (client path) + per-artifact selection
**As** a board user, **I want** each artifact summarized through the Router and to pick its
own model/engine, **so that** summaries are consistent and configurable.
**Acceptance:**
- Dropping/picking an artifact runs `aiRouter.runJob({kind:'summarize'}, selection)`; result
  saved to `comms_artifacts.summary`.
- `comms_artifacts` gains a persisted `summary_selection` (`{type,id}`); a re-summarize action exists.
- The old `localStorage` upload-summary dropdown is replaced by the unified selector.
*Delivered by:* Conversation 3.

## US-4 — Server-triggered summary without server-side inference
**As** the pipeline, **when** an agent attaches an artifact mid-run, **I want** the summary
to run on the connected client, **so that** the server never runs inference or a CLI subprocess.
**Acceptance:**
- Server enqueues a summary request (runner SSE / board), the client runs the Router and posts
  the result back to `comms_artifacts.summary`.
- With no client connected, the artifact stays filename-only (best-effort) — no server inference.
*Delivered by:* Conversation 4.

## US-5 — Remove the old summarizer (cleanup)
**As** a maintainer, **I want** the replaced code deleted, **so that** no dead parallel path remains.
**Acceptance:**
- `runner/inference.py` (minilm/ollama/haiku) + its callers removed.
- `app_settings` `inference:summary_backend` / `inference:ollama_model` + helpers removed.
- `Settings/SummarySettings.tsx` + its API helpers removed.
- `test_inference.py`, `test_summary_backend.py`, `test_comms_artifact_summarize.py` removed or rewritten.
- New tests cover `aiRouter`, `modelManager` dispatch, and the server-trigger handoff.
- `python -m pytest -q` and both `tsc` configs pass; no references to deleted symbols remain.
*Delivered by:* Conversation 5.

## US-6 — Phase-boundary board posts (both modes)
**As** a board user, **I want** each pipeline phase boundary to appear on the feature board,
**so that** the Command Center shows live progress in interactive AND headless runs.
**Acceptance:**
- The server `record-phase` handler posts a `phase`-type board message on PHASE_START/PHASE_DONE
  (best-effort; never blocks phase logging).
- `phase` messages are UI-visible but **EXCLUDED** from prompt-injected board context
  (`retrieve_board_context`), so headless CLI-engine prompts do not grow.
- Interactive (`team-http`) and headless (supervisor) populate the board identically — no
  skill-only divergence; no change to CLI-engine execution.
*Delivered by:* Conversation 6.
