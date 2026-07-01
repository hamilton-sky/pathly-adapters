---
name: Implementation Plan
---
# BrightSky Agent Upgrade — Implementation Plan

## Overview

Extends the BrightSky ↔ Pathly Studio integration with 7 new studio bridge tools (list_plans, get_events, get_failures, create_plan, navigate_to, run_skill, get_layout), fixes the HQ Reasoning box for BrightSky messages, enables web/YouTube search for the Pathly agent, and replaces fake thinking with real Gemini `thinkingConfig` (BrightSky uses Gemini 2.5 Flash — not Claude). Changes span two repos: `pathly-adapters` (Studio) and `brightsky-ai` (backend).

## Layer Architecture

```
BrightSky backend (brightsky-ai)           Pathly Studio (pathly-adapters)
  PathlyRouterService                          studioAnalyzer.ts
      │  tool_call WebSocket msg                   │  executeStudioTool()
      ▼                                            ▼
  StudioBridgeTool subclasses              window.pathly.fs.* / fsm.* / __pathlyNavigate
  (studio-bridge-tool.ts)                  (IPC → main process → filesystem / FSM HTTP)
      │  tool_response WebSocket msg
      ▼
  Gemini 2.5 Flash via gemini.service.ts
  (thinkingConfig enabled for pathly_chat)
      │  thinking content parts → <think>…</think> stream_chunk
      ▼
  Studio brightskyClient.ts
  stream_end → splitThinkingContent() → msg.thinking
      ▼
  ThinkingBlock.tsx — Reasoning collapsible
```

---

## Phases

### Phase 0 — Pre-flight check   ← Conversation: 1
**File:** `studio/src/renderer/src/lib/studioAnalyzer.ts`
**Done when:** Existing 4 tool handlers confirmed present in `studioTools` registry; `npm run typecheck` exits 0 with no new errors as baseline.
**Details:**
- Read `studioAnalyzer.ts` and confirm the `studioTools` registry at the bottom of the file contains exactly: `get_fsm_state`, `studio.get_fsm_state`, `get_feature_plan`, `studio.get_feature_plan`, `get_studio_schema`, `studio.get_studio_schema`, `automation:executeStep`, `studio.automation.executeStep`
- Run `npm run typecheck` from the repo root (`C:\Users\Yafit\pathly-adapters`) and record any pre-existing errors as baseline — do not fix them in this phase
- Confirm `window.pathly.fs.list`, `window.pathly.fs.listDirs`, `window.pathly.fs.read`, `window.pathly.fs.write` are all declared in `global.d.ts`

---

### Phase 1 — `studio.list_plans` tool   ← Conversation: 1
**File:** `studio/src/renderer/src/lib/studioAnalyzer.ts`
**Done when:** `executeStudioTool('studio.list_plans', {})` returns `{ plans: [...], success: true }` for a project with plans.
**Delivers stories:** S-01
**Depends on:** Phase 0
**Enables:** Phase 9 (backend registration)
**Details:**
- Add `async function listPlans()` that:
  1. Gets `projectPath` from `useProjectStore.getState()`
  2. Calls `window.pathly.fs.listDirs(\`${projectPath}/pathly/plans\`)` to get folder names
  3. Filters out `.archive` and any non-directory entries
  4. For each folder, attempts `window.pathly.fs.read(\`${projectPath}/pathly/plans/${name}/STATE.json\`)`, parses JSON, extracts `state` field as `fsmStage`
  5. Returns `{ plans: [{ name, fsmStage, status: 'active' }], success: true }` — catch all errors per-plan, never bubble up
- Register as `'studio.list_plans'` in `studioTools`
**Verify:** `npm run typecheck` from repo root exits 0

---

### Phase 2 — `studio.get_events` tool   ← Conversation: 1
**File:** `studio/src/renderer/src/lib/studioAnalyzer.ts`
**Done when:** `executeStudioTool('studio.get_events', { limit: 5 })` returns last 5 lines of EVENTS.jsonl for the active feature.
**Delivers stories:** S-02
**Depends on:** Phase 0
**Enables:** Phase 9
**Details:**
- Add `async function getEvents(params: unknown)` that:
  1. Extracts `feature?: string` and `limit?: number` from params (default: active topic, limit 20, cap at 50)
  2. Reads `${projectPath}/pathly/plans/${feature}/EVENTS.jsonl` via `safeRead()` with `maxChars` = limit × 200
  3. Splits by newline, takes last `limit` lines, rejoins
  4. Returns `{ events: string, success: true }` — returns `{ events: '', success: true }` when file absent
- Register as `'studio.get_events'`
**Verify:** `npm run typecheck` exits 0

---

### Phase 3 — `studio.get_failures` tool   ← Conversation: 1
**File:** `studio/src/renderer/src/lib/studioAnalyzer.ts`
**Done when:** `executeStudioTool('studio.get_failures', { type: 'all' })` returns review and test failure content (or empty strings).
**Delivers stories:** S-03
**Depends on:** Phase 0
**Enables:** Phase 9
**Details:**
- Add `async function getFailures(params: unknown)` that:
  1. Extracts `feature?: string` and `type: 'review' | 'test' | 'all'` (default `'all'`)
  2. Reads from `${projectPath}/pathly/plans/${feature}/feedback/` via `safeRead` — 3000 char limit each
  3. Returns `{ review: string, test: string, success: true }` — empty strings when files absent
- Register as `'studio.get_failures'`
**Verify:** `npm run typecheck` exits 0

---

### Phase 4 — `studio.create_plan` tool   ← Conversation: 1
**File:** `studio/src/renderer/src/lib/studioAnalyzer.ts`
**Done when:** `executeStudioTool('studio.create_plan', { featureName: 'test-feature' })` creates STATE.json and USER_STORIES.md under `pathly/plans/test-feature/`.
**Delivers stories:** S-04
**Depends on:** Phase 0
**Enables:** Phase 9
**Details:**
- Add `async function createPlan(params: unknown)` that:
  1. Extracts `featureName: string` and optional `description?: string`
  2. Checks if folder exists via `window.pathly.fs.listDirs(\`${projectPath}/pathly/plans\`).includes(featureName)` — returns `{ success: false, error: 'Plan already exists' }` if so
  3. Writes `pathly/plans/${featureName}/STATE.json` with `{ "state": "PLAN", "feature": featureName, "rigor": "standard" }`
  4. Writes `pathly/plans/${featureName}/USER_STORIES.md` with a minimal template (feature name header + one empty story stub)
  5. Returns `{ path: \`pathly/plans/${featureName}\`, success: true }`
- Note: verify that `window.pathly.fs.write` creates parent directories (check `fs.ts` IPC handler). If not, write a helper that calls `window.pathly.fs.write` after ensuring the path is reachable — the simplest fix is checking the main-process `fs:write` handler and adding `fs.mkdirSync(dirname(path), { recursive: true })` before write.
- Register as `'studio.create_plan'`
**Verify:** `npm run typecheck` exits 0

---

### Phase 5 — `studio.navigate_to` tool   ← Conversation: 1
**File:** `studio/src/renderer/src/lib/studioAnalyzer.ts`
**Done when:** `executeStudioTool('studio.navigate_to', { panel: 'monitor' })` calls `window.__pathlyNavigate('monitor')` without error.
**Delivers stories:** S-05
**Depends on:** Phase 0
**Enables:** Phase 9
**Details:**
- Add `async function navigateTo(params: unknown)` that:
  1. Extracts `panel: string` from params
  2. Calls `window.__pathlyNavigate?.(panel)` — using optional chaining since the function may not be bound at call time
  3. Returns `{ success: true }` if function exists; `{ success: false, error: 'navigate not available' }` otherwise
- Before implementing: search renderer source for `__pathlyNavigate` assignments to confirm valid panel names — add a comment listing them as a guide for the backend
- Register as `'studio.navigate_to'`
**Verify:** `npm run typecheck` exits 0

---

### Phase 5a — `studio.get_layout` tool   ← Conversation: 1
**File:** `studio/src/renderer/src/lib/studioAnalyzer.ts`
**Done when:** `executeStudioTool('studio.get_layout', {})` returns a manifest with `panels`, `buttons` (all 7 HQ controls with data-labels), live `currentPanel`, `fsmStage`, `runnerStatus`.
**Delivers stories:** S-06
**Depends on:** Phase 0
**Enables:** Phase 9 (backend registration)
**Details:**
- Add `async function getLayout()` that builds a static + live manifest:
  1. **Static part** — hardcoded from known Pathly UI structure:
     - `panels`: `['monitor', 'plan', 'chat', 'flow', 'terminal']`
     - `buttons`: array of `{ label, dataLabel, panel, action }` for all HQ controls — read `studio/src/renderer/src/components/HQ/` to confirm the exact `data-label` values for: start, go, pause, ff, help, team, end
  2. **Live part** — read from Zustand stores at call time:
     - `currentPanel`: from `useUiStore.getState().activePanel`
     - `activeFeature`: from `useProjectStore.getState().activeTopic`
     - `fsmStage`: from cached FSM state or `'unknown'` if unavailable
     - `runnerStatus`: from `useRunnerStore.getState().status` (check store name — search for `runnerStore` or `RunnerStatus` in store directory)
     - `terminalTabs`: from `useTerminalStore.getState()` — map open tabs to `{ id, label, kind }`
  3. Returns `{ layout: { panels, buttons, currentPanel, activeFeature, fsmStage, runnerStatus, terminalTabs }, success: true }`
- Register as both `'studio.get_layout'` and `'get_layout'` for consistency with other dual-name registrations
**Verify:** `npm run typecheck` exits 0

---

### Phase 6 — `fsm:runSkill` IPC handler   ← Conversation: 2
**File:** `studio/src/main/ipc/fsm.ts`
**Done when:** `ipcMain.handle('fsm:runSkill', ...)` is registered and POSTs to `${FSM_BASE}/runner/start` with a valid body.
**Delivers stories:** S-07 (partial)
**Depends on:** Phase 0
**Enables:** Phase 7
**Details:**
- Before implementing: read `studio/src/renderer/src/components/` to find `FlowControlBar` — locate the `POST /runner/start` call and extract the exact request body shape
- Add `ipcMain.handle('fsm:runSkill', async (_event, topic: string, skill: string, projectPath: string))` to `registerFsmHandlers()` in `fsm.ts`
- POST to `${FSM_BASE}/runner/start` with the same body format as FlowControlBar
- Return `{ success: boolean, runId?: string, error?: string }`
**Verify:** `npm run typecheck -p studio/tsconfig.node.json` exits 0

---

### Phase 7 — `run_skill` preload + type + studioAnalyzer   ← Conversation: 2
**File:** `studio/src/main/preload/index.ts`, `studio/src/renderer/src/types/global.d.ts`, `studio/src/renderer/src/lib/studioAnalyzer.ts`
**Done when:** `window.pathly.fsm.runSkill` is callable from renderer; `executeStudioTool('studio.run_skill', { feature: 'x', skill: 'build' })` returns `{ success: true, runId: '...' }`.
**Delivers stories:** S-06 (complete)
**Depends on:** Phase 6
**Enables:** Phase 9
**Details:**
- In `preload/index.ts`: add `runSkill: (topic: string, skill: string, projectPath: string): Promise<unknown> => ipcRenderer.invoke('fsm:runSkill', topic, skill, projectPath)` to the `fsm` object
- In `global.d.ts`: add `runSkill: (topic: string, skill: string, projectPath: string) => Promise<{ success: boolean; runId?: string; error?: string }>` to the `fsm` type
- In `studioAnalyzer.ts`: add `async function runSkill(params: unknown)` that extracts `{ feature, skill }`, gets `projectPath` from store, calls `window.pathly.fsm.runSkill(feature, skill, projectPath)`, and registers as `'studio.run_skill'`
**Verify:** `npm run typecheck` exits 0

---

### Phase 8 — Reasoning box: BrightSky stream_end fix   ← Conversation: 2
**File:** `studio/src/renderer/src/lib/brightskyClient.ts`
**Done when:** When BrightSky sends a message containing `<think>reasoning here</think>Response here`, the ThinkingBlock on that message shows "reasoning here" collapsed and the visible response shows "Response here".
**Delivers stories:** S-07
**Depends on:** Phase 0
**Enables:** Phase 12 (backend thinking stream)
**Details:**
- Import `splitThinkingContent` from the thinkingParser module (find its path — likely `'./thinkingParser'` or check useHQ.tsx line 135 import)
- In the `stream_end` handler (lines 95-98): before clearing `streamContent`, call:
  ```ts
  const { thinking, content } = splitThinkingContent(this.streamContent)
  useChatStore.getState().updateLastMessage({ content: content || this.streamContent, thinking, status: 'done' })
  ```
- In the `stream_chunk` handler's `isDone === true` branch (line 91-94): same call — `splitThinkingContent(this.streamContent)` and update with `{ content, thinking, status: 'done' }` instead of just `{ content: this.streamContent }`
- Do NOT touch the `status: 'streaming'` update mid-stream — only apply `splitThinkingContent` at stream end
**Verify:** `npm run typecheck` exits 0

---

### Phase 9 — BrightSky: 6 new StudioBridgeTool subclasses   ← Conversation: 3
**File:** `C:\Users\Yafit\brightsky-ai\backend\src\mcp\tools\studio-bridge-tool.ts`
**Done when:** Six new classes (`ListPlansTool`, `GetEventsTool`, `GetFailuresTool`, `CreatePlanTool`, `NavigateToTool`, `RunSkillTool`) exist in the file and extend `StudioBridgeTool` with correct `toolName`.
**Delivers stories:** S-09 (partial)
**Depends on:** Phase 0 (pre-flight baseline)
**Enables:** Phase 10
**Details:**
- Read the file first — understand the base class pattern (`StudioBridgeTool.execute()` → `sendStudioToolCall()` → wait for `tool_response`)
- Add one class per tool following the existing pattern (look at `GetFsmStateTool` or `GetFeaturePlanTool` as the template):
  - `ListPlansTool` → `toolName = 'studio.list_plans'`
  - `GetEventsTool` → `toolName = 'studio.get_events'`
  - `GetFailuresTool` → `toolName = 'studio.get_failures'`
  - `CreatePlanTool` → `toolName = 'studio.create_plan'`
  - `NavigateToTool` → `toolName = 'studio.navigate_to'`
  - `RunSkillTool` → `toolName = 'studio.run_skill'`
  - `GetLayoutTool` → `toolName = 'studio.get_layout'`
- Each class only needs `toolName` and `description` — parameter passing to Studio is generic via `sendStudioToolCall(parameters)`
**Verify:** `npx tsc --noEmit` in `C:\Users\Yafit\brightsky-ai\backend\` exits 0

---

### Phase 10 — BrightSky: register all 7 tools   ← Conversation: 3
**File:** `C:\Users\Yafit\brightsky-ai\backend\src\mcp\mcp.module.ts`
**Done when:** All 7 new tools appear in the tool provider array near line 365; TypeScript build passes.
**Delivers stories:** S-09 (complete)
**Depends on:** Phase 9
**Enables:** Phase 10a
**Details:**
- Find the tool provider array in `mcp.module.ts` (near line 365) where existing studio tools are registered
- Add all 7 new classes: `ListPlansTool`, `GetEventsTool`, `GetFailuresTool`, `CreatePlanTool`, `NavigateToTool`, `RunSkillTool`, `GetLayoutTool`
- Follow the exact same provider registration pattern as existing studio tools
**Verify:** `npx tsc --noEmit` in `C:\Users\Yafit\brightsky-ai\backend\` exits 0

---

### Phase 10a — BrightSky: Pathly agent routing in UnifiedAIService   ← Conversation: 3
**File:** `C:\Users\Yafit\brightsky-ai\backend\src\services\unified-ai.service.ts`
**Done when:** For `messageType === 'pathly_chat'`, the UnifiedAIService always routes to Gemini; `web_search`, `youtube_search`, and `youtube_transcript` tools are included in the Pathly available-tool set.
**Delivers stories:** S-10
**Depends on:** Phase 10
**Enables:** Phase 11
**Details:**
- Read `unified-ai.service.ts` — find the routing logic (near lines 345-387) that selects provider based on task type
- Add a guard at the top of provider selection: if `context.messageType === 'pathly_chat'` (or however messageType flows into this service — trace from WsMessageHandler), force `provider = 'gemini'` and skip the routing logic. Gemini is required because it supports `thinkingConfig` (Phase 11)
- Find where available tools are constructed for a session — add `web_search`, `youtube_search`, `youtube_transcript` to the tool set when `messageType === 'pathly_chat'`
- Add an explicit comment: `// Pathly messages always use Gemini for thinkingConfig support`
- Non-Pathly messages are unaffected — their routing logic and tool sets are unchanged
**Verify:** `npx tsc --noEmit` in `C:\Users\Yafit\brightsky-ai\backend\` exits 0

---

### Phase 11 — BrightSky: add Gemini thinkingConfig for Pathly   ← Conversation: 4
**File:** `C:\Users\Yafit\brightsky-ai\backend\src\services\gemini.service.ts`
**Done when:** For `messageType === 'pathly_chat'`, the Gemini `generateContentStream()` call includes `thinkingConfig: { thinkingBudget: 8000 }` and thinking content parts are captured from the stream.
**Delivers stories:** S-11 (partial)
**Depends on:** Phase 10a
**Enables:** Phase 12
**Details:**
- Read `gemini.service.ts` — find `generateContentStream()` (near line 1353) and understand how it is called
- Trace how `messageType` flows from `WsMessageHandler` → `UnifiedAIService` → `gemini.service.ts` — add a `pathlyMode?: boolean` param or pass `messageType` through the call chain as needed
- In `generateContentStream()`: add conditional — if `pathlyMode` is true, add `generationConfig: { thinkingConfig: { thinkingBudget: 8000 } }` to the request
- Capture thinking content parts from the streamed response — Gemini 2.5 Flash returns them as parts with `thought: true` flag or a dedicated thinking part type. Check the Gemini SDK response shape for thinking content
- Pass captured thinking text to Phase 12 streaming logic
**Verify:** `npx tsc --noEmit` in `C:\Users\Yafit\brightsky-ai\backend\` exits 0

---

### Phase 12 — BrightSky: stream Gemini thinking as `<think>` tags   ← Conversation: 4
**File:** `C:\Users\Yafit\brightsky-ai\backend\src\chat\gateways\session\services\reasoning-timer.service.ts`
**Done when:** For Pathly messages, Gemini thinking parts are sent to Studio as early `stream_chunk` messages with `<think>...</think>` wrapping; synthetic timer steps do not fire for `pathly_chat` messages.
**Delivers stories:** S-11 (complete)
**Depends on:** Phase 11
**Enables:** S-08 (the Studio-side Reasoning box)
**Details:**
- In `reasoning-timer.service.ts`: add a guard — if `messageType === 'pathly_chat'`, return immediately and skip all synthetic thinking step generation
- In the streaming pipeline from Phase 11: when a Gemini thinking part arrives, emit a `stream_chunk` WebSocket message with content `<think>${thinkingText}</think>` BEFORE the first text content chunk is sent. Use the same send mechanism used by `response-delivery.service.ts` for regular stream_chunks
- The `<think>` chunk MUST arrive at the Studio client before any visible text chunks — this is what triggers the ThinkingBlock to appear
**Verify:** `npx tsc --noEmit` in `C:\Users\Yafit\brightsky-ai\backend\` exits 0

---

## Prerequisites
- BrightSky WebSocket connection is active (existing `studio.get_fsm_state` tool works end-to-end)
- `npm run typecheck` baseline is recorded before Conv 1 begins (Phase 0)
- `npx tsc --noEmit` baseline in `brightsky-ai/backend` is recorded before Conv 3 begins

## Key Decisions

### Decision 1: No new IPC channels for read tools (list_plans, get_events, get_failures)
All three read tools use the existing `window.pathly.fs.read()` and `window.pathly.fs.listDirs()` IPC channels. No new channels are needed. This keeps Conv 1 entirely within `studioAnalyzer.ts` — one file, no cross-process coordination.

### Decision 2: New IPC channel only for run_skill
`studio.run_skill` needs to POST to the FSM HTTP server from the main process (not renderer, to avoid CORS). This is the only tool that requires a new IPC channel — kept isolated in Conv 2.

### Decision 3: splitThinkingContent called only at stream end
The `<think>` tags may span multiple chunks. We do not attempt mid-stream parsing — only call `splitThinkingContent` when `isDone === true` or `stream_end` fires. This matches how Conductor (Claude Code) handles thinking.

### Decision 4: Gemini 2.5 Flash is the Pathly agent model (not Claude)
BrightSky does NOT call Claude/Anthropic. Its primary model is Gemini 2.5 Flash via `gemini.service.ts`. The `@anthropic-ai/sdk` is in `package.json` but has zero imports. Extended thinking uses Gemini's `thinkingConfig: { thinkingBudget: 8000 }` — not Anthropic's `thinking: { type: 'enabled' }`. Gemini is pinned for Pathly messages because it is the only provider in the stack with thinkingConfig support.

### Decision 5: studio.get_layout returns a static manifest + live state
The layout tool does not analyze the DOM at runtime (unlike BrightSky's 23 PageAnalyzer tools for generic web pages). Instead it returns a hardcoded list of known Pathly UI elements (panels, data-labels, button purposes) merged with live Zustand state. This is faster, more reliable, and gives the agent richer semantic context about what buttons do — not just what they are.
