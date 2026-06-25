# Conversation Prompts — unified-ai-routing

> Builder prompts. Each references STORM_SEED.md + ARCHITECTURE_PROPOSAL.md. Respect SOLID
> rules (400-line Python cap, ~150-line TS component cap, one component per subfolder, no
> inline styles, layer dependency rule).

## Conversation 1 — AI Model Manager
Extract an app-level `modelManager` service from HQ. Move ownership of the model catalog
(`WEB_LLM_MODELS`) into `services/modelManager/`, and expose `runModel(id, prompt) →
{text, cost_usd?}` dispatching Ollama (HTTP 127.0.0.1:11434), GGUF (via `llmBridge` IPC to
main), Brightsky (via `brightskyClient`). Refactor `HQ/ModelSelector` + `store/modelStore`
to consume it. **Do not change HQ chat behavior.** Verify HQ still works + `npm run typecheck`.

## Conversation 2 — Router + unified selector
Add `services/aiRouter.ts` with `runJob(job, selection)`: `selection.type==='model'` →
`modelManager.runModel`; `==='engine'` → `terminal.spawn(tabId, cwd, undefined,
buildHeadlessArgv(adapter, prompt))` and read the result. Add `AiTargetSelector/` — one
dropdown listing models ⊕ `ADAPTER_META` engines. No API-key path. Add a unit test for both
branches. Verify typecheck.

## Conversation 3 — Board summary via Router + per-artifact selection
Add `summary_selection` (JSON) column to `comms_artifacts` (`db/migrations.py` +
`db/queries/comms.py`). Wire `ArtifactsView` to use `AiTargetSelector` and call
`aiRouter.runJob({kind:'summarize', text}, selection)`, writing the result to
`comms_artifacts.summary`. Add a re-summarize action. Replace the `pathly.comms.uploadSummary`
localStorage dropdown. App default in `app_settings` (`ai_routing:default_summary_selection`).
Verify drop → summary via chosen target; selection persists per artifact.

## Conversation 4 — Server-triggered summary (no server inference)
On mid-run artifact attach, the server emits a summary-request event (runner SSE / board)
instead of calling `summarize_async`. The renderer subscribes, runs `aiRouter`, and POSTs
the result back (`update_artifact_summary`). Best-effort when no client is connected
(filename-only). The server must run NO inference and NO CLI subprocess. Verify the handoff.

## Conversation 5 — Cleanup + tests
Delete `runner/inference.py` + callers (`runner/hydrate.py`, `blueprints/comms/artifacts.py`).
Delete `app_settings` `inference:*` helpers/keys. Delete `Settings/SummarySettings.tsx` +
`apiGet/SetSummaryBackend`. Remove/rewrite `test_inference.py`, `test_summary_backend.py`,
`test_comms_artifact_summarize.py`. Add tests for `aiRouter` dispatch, `modelManager`
transport selection, and the server-trigger handoff. Verify `pytest -q` + both `tsc` configs
green; `grep` confirms no references to deleted symbols.

## Conversation 6 — Phase-boundary board posts (both modes)
Make the server `record-phase` handler post a `phase`-type board message to the feature board on
PHASE_START/PHASE_DONE (best-effort, never block phase logging). Exclude `phase` messages from
`retrieve_board_context` (`runner/comms_context.py`) so headless CLI-engine prompts stay lean. Add
`phase` to the message-type set + a minimal Command-Center affordance. Verify both interactive and
headless runs populate the board, and that injected board context excludes phase posts (no prompt
bloat, no change to CLI-engine execution).
