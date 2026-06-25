# PO Notes — unified-ai-routing

> Captured from the user directly (no live PO session). This is the authoritative
> requirements brief for the architect storm and planner.

## Problem

AI dispatch in Studio is fragmented across **three disconnected systems**, and one of
them is broken:

1. **HQ chat model picker** — rich. Catalog in `studio/src/renderer/src/data/models.ts`
   (`WEB_LLM_MODELS`), engines in `studio/src/main/ipc/llm.ts` (`MODEL_REGISTRY`, GGUF +
   Ollama), selection in `studio/src/renderer/src/store/modelStore.ts`, plus Brightsky
   over a renderer WebSocket (`lib/brightskyClient.ts`).
2. **CLI-engine spawn** — the editor/board action buttons (Split, Analyze, Evaluate,
   Send-comment) spawn a CLI engine client-side via `window.pathly.terminal.spawn` +
   `buildHeadlessArgv` (`services/cliEngine.ts`, `ADAPTER_META`). Runs in the user's
   Electron environment; CLI auth is whatever the user logged into. **No API key.**
3. **Summary backend** — a *separate, server-side* path in
   `src/pathly_orchestrator/runner/inference.py` with its own private 3-bucket model idea
   (`minilm`/`ollama`/`haiku`) and app_settings keys (`inference:summary_backend`,
   `inference:ollama_model`). Its `haiku` branch shells out to the `claude` CLI **from the
   Python FSM server**, which fails on Windows: `claude CLI not found on the server PATH`.

The summary system is the odd one out and is architecturally wrong.

## Target design — three single-responsibility pieces

1. **CLI Engine** — keep exactly as-is (`terminal.spawn` + `buildHeadlessArgv` +
   `ADAPTER_META`). Spawns claude/codex/antigravity/copilot in the user's env. Untouched.
2. **AI Model Manager** — lift the HQ model system (Ollama / GGUF / Brightsky) out of the
   HQ component into an app-level manager (single source of truth for "what models exist +
   how to reach each").
3. **Router** — a small component that, given a job + a user selection, dispatches to
   **either** the CLI Engine **or** the AI Model Manager. Selection is "a model OR a CLI
   engine."

**Consumer:** board artifacts. Auto-summary and a **per-artifact** model/engine selection
both go through the Router. "Summarize" stops being a special feature — it's just "send the
file + a summarize message" through the Router, identical to how Split/Analyze/Evaluate work.

## Hard requirements

- **No Anthropic API key anywhere.** CLI engines self-auth; models use their own transports
  (Ollama HTTP, GGUF in-process, Brightsky WS). An API-key path is explicitly rejected.
- **Server-triggered summaries** (an agent attaches a file mid-pipeline, no UI in the loop)
  must reuse the **existing `TERMINAL_SPAWN` pipeline** — server emits a spawn request,
  Studio runs it, result posts back to `comms_artifacts.summary`. The server must NOT run a
  CLI subprocess or call an inference engine itself.
- **Per-artifact selection must persist** — today the "Upload summary" dropdown is only a
  sticky `localStorage` value (`pathly.comms.uploadSummary`), applied at upload time, not
  saved per artifact. Needs to be stored per artifact with a re-summarize action.
- **Cleanup is a required acceptance criterion.** After the new path works, REMOVE the
  replaced code: `runner/inference.py`'s `minilm`/`ollama`/`haiku` summarizer, the
  `inference:summary_backend` / `inference:ollama_model` app_settings + their query helpers,
  `Settings/SummarySettings.tsx`'s 3-bucket picker, and any now-dead callers/tests. No dead
  parallel path may remain.

## Constraints

- SOLID rules from CLAUDE.md: 400-line hard cap (Python), ~150-line cap (TS components),
  one component per subfolder, layer dependency rule, no inline styles.
- Transport reachability matters: the Python server can reach Ollama HTTP; it CANNOT reach
  GGUF (Electron main) or the Brightsky renderer socket — those must route via spawn/IPC.
- Studio responsiveness rules (resize, min-width:0) for any new UI.

## Out of scope (for this feature)

- Per-agent / per-stage model routing for the FSM pipeline itself (`stage_configs`,
  flow `role_map`) — that is a separate existing system; do not fold it in here.
- Re-architecting the HQ chat UX beyond extracting the Model Manager it depends on.

## Key reference files

- `studio/src/renderer/src/components/CommandCenter/CommsPanel/ArtifactsView/ArtifactsView.tsx`
- `studio/src/renderer/src/components/Settings/SummarySettings.tsx`
- `studio/src/renderer/src/components/HQ/ModelSelector/ModelSelector.tsx`
- `studio/src/renderer/src/store/modelStore.ts`, `data/models.ts`
- `studio/src/renderer/src/services/cliEngine.ts`
- `studio/src/renderer/src/components/MarkdownEditor/EditorHeader/hooks/useEditorAgentActions.ts`
- `src/pathly_orchestrator/runner/inference.py`
- `src/pathly_orchestrator/db/queries/app_settings.py`
