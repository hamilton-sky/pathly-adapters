# Implementation Plan — unified-ai-routing

Rigor: standard. Mode: fast (auto-flow). Layers: Python (db/runner/http_server/supervisor) + Studio (renderer/main).

See `ARCHITECTURE_PROPOSAL.md` for the component contract and `FLOW_DIAGRAM.md` for the dispatch/trigger flows.

## Conversation 1 — AI Model Manager (extract from HQ)
**Fulfills:** US-1.
- New `studio/src/renderer/src/services/modelManager/` — single catalog (move/own `WEB_LLM_MODELS`)
  + `runModel(id, prompt)` dispatch (Ollama HTTP / GGUF via `llmBridge` IPC / Brightsky via `brightskyClient`).
- Refactor `HQ/ModelSelector` + `store/modelStore` to consume `modelManager` (no HQ behavior change).
- **Verify:** HQ chat still selects/streams from each backend; `npm run typecheck`.

## Conversation 2 — Router + unified selector
**Fulfills:** US-2.
- New `studio/src/renderer/src/services/aiRouter.ts` — `runJob(job, selection)`:
  `model` → `modelManager.runModel`; `engine` → `terminal.spawn(buildHeadlessArgv(...))` + result read.
- New `components/.../AiTargetSelector/` — one dropdown: models ⊕ `ADAPTER_META` engines.
- **Verify:** unit test routes both branches; selector renders both groups; typecheck.

## Conversation 3 — Board summary via Router + per-artifact selection
**Fulfills:** US-3.
- DB: add `summary_selection` (TEXT/JSON) to `comms_artifacts` (`db/migrations.py` + `db/queries/comms.py`).
- Renderer: `ArtifactsView` uses `AiTargetSelector`; dropping/re-summarizing calls `aiRouter`,
  writes result to `comms_artifacts.summary`; remove `pathly.comms.uploadSummary` localStorage dropdown.
- App default selection in `app_settings` (`ai_routing:default_summary_selection`).
- **Verify:** drop a .md artifact → summary appears via chosen target; per-artifact pick persists.

## Conversation 4 — Server-triggered summary (no server inference)
**Fulfills:** US-4.
- Server: on artifact attach during a run, emit a summary-request event (runner SSE / board signal)
  instead of calling `summarize_async`.
- Renderer: subscribe, run `aiRouter`, POST result back (`update_artifact_summary`).
- Best-effort when no client connected (filename-only).
- **Verify:** simulate a mid-run attach → client summarizes → DB updated; with client off → no server inference.

## Conversation 5 — Cleanup + tests
**Fulfills:** US-5.
- Delete `runner/inference.py` + callers (`runner/hydrate.py`, `blueprints/comms/artifacts.py`).
- Delete `app_settings` `inference:*` helpers/keys; delete `Settings/SummarySettings.tsx` + API helpers.
- Remove/rewrite `test_inference.py`, `test_summary_backend.py`, `test_comms_artifact_summarize.py`.
- Add tests: `aiRouter` dispatch, `modelManager` transport selection, server-trigger handoff.
- **Verify:** `python -m pytest -q` green; both `tsc` configs clean; `grep` shows no references to deleted symbols.

## Conversation 6 — Phase-boundary board posts (both modes)
**Fulfills:** US-6.
- Server: in the `record-phase` handler (`http_server/blueprints/.../telemetry.py`), post a
  `phase`-type board message (feature scope) on PHASE_START/PHASE_DONE — best-effort, never block.
- `runner/comms_context.py`: exclude `phase` type from `retrieve_board_context` injection.
- Add `phase` to the board message-type set + a minimal Command-Center render affordance.
- **Verify:** an interactive run AND a headless run both show a phase timeline on the board;
  headless agent prompts (`retrieve_board_context`) do NOT include phase posts → no prompt bloat.
- *Note:* board-observability, adjacent to routing — kept last so it never blocks the core.

## Sequencing
1 → 2 → 3 → 4 → 5 → 6. Conversations 1–2 are additive (no deletes); deletes happen only in 5,
after the new path is proven in 3–4. Conversation 6 is independent (board observability) and can
run any time after the board plumbing is stable.
