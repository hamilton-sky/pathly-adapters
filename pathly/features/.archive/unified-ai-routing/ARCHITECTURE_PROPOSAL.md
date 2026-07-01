# Architecture Proposal — unified-ai-routing

> Auto-added by rigor escalator: cross-layer dependency signal (Python + Studio).

## Components & contracts

### CLI Engine (existing — unchanged)
- `services/cliEngine.ts`: `buildHeadlessArgv(adapter, prompt, opts)`, `ADAPTER_META`.
- `window.pathly.terminal.spawn(tabId, cwd, undefined, argv)` → `main/ipc/terminal.ts` scheduler.
- Auth: user's CLI login. Process: user's Electron env.

### AI Model Manager (new — extracted from HQ)
- `services/modelManager/` (renderer).
- **Owns:** the catalog (one `Model[]`, moved from `data/models.ts`), availability state.
- **API:** `runModel(id: string, prompt: string): Promise<{ text: string; cost_usd?: number }>`.
- **Dispatch by transport:** Ollama → HTTP `127.0.0.1:11434`; GGUF → `llmBridge` IPC (main);
  Brightsky → `brightskyClient` WS.
- **Consumers:** HQ `ModelSelector` (refactored), `aiRouter`.

### Router (new — small)
- `services/aiRouter.ts`.
- **API:** `runJob(job: AiJob, selection: AiSelection): Promise<AiResult>`.
  - `AiSelection = { type: 'model' | 'engine'; id: string }`
  - `AiJob = { kind: 'summarize' | …; text?: string; prompt?: string; cwd?: string }`
  - `type==='model'` → `modelManager.runModel(id, prompt)`.
  - `type==='engine'` → CLI Engine spawn (`buildHeadlessArgv(id, prompt)`), resolve on PTY exit.
- **No** Anthropic API-key transport.

### Consumer — board artifacts
- DB: `comms_artifacts.summary_selection` (JSON `{type,id}`), `comms_artifacts.summary` (result).
- App default: `app_settings['ai_routing:default_summary_selection']`.

## Layer dependency (no upward imports)
- Python: `db → runner → supervisor → http_server` (unchanged). Server emits summary-request
  events; it does **not** import an inference module (that module is deleted).
- Studio: `modelManager` and `cliEngine` are leaf services; `aiRouter` depends on both;
  UI (HQ, ArtifactsView) depends on `aiRouter`/`modelManager`. No cycles.

## Migration / compat
- Existing `comms_artifacts.summary` rows untouched; `summary_selection` nullable → app default.
- Removed app_settings keys (`inference:summary_backend`, `inference:ollama_model`) have no
  replacement readers after Conv 5; default selection key supersedes them.

## Out of scope
- FSM per-stage/per-agent model routing (`stage_configs`, flow `role_map`) — separate system.
