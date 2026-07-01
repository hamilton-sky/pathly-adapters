---
name: Conversation Guide
---
# BrightSky Agent Upgrade — Conversation Guide

Split into 4 conversations (max 4). Each produces runnable, type-checked code.
After each conversation, **commit your changes** before starting the next.

---

## Conversation 1: Studio — 5 new read/write tool handlers (Phases 0–5)

**Stories delivered:** S-01, S-02, S-03, S-04, S-05

**Prompt to paste:**
```
Read pathly/plans/brightsky-agent-upgrade/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement BrightSky Agent Upgrade — Conversation 1 (Phases 0–5) from pathly/plans/brightsky-agent-upgrade/IMPLEMENTATION_PLAN.md.

This conversation works entirely in ONE file: studio/src/renderer/src/lib/studioAnalyzer.ts

**Before editing anything:** glob/read the live repo to confirm:
- studio/src/renderer/src/lib/studioAnalyzer.ts exists
- studio/src/renderer/src/types/global.d.ts has window.pathly.fs.list, listDirs, read, write
- Run npm run typecheck from repo root and record any pre-existing errors as baseline (Phase 0)

**Scope:**

Phase 1 — Add `studio.list_plans` tool:
- Add `async function listPlans()` using `window.pathly.fs.listDirs()` on the plans directory
- Filter out `.archive`; for each folder read STATE.json to extract `fsmStage`
- Returns `{ plans: [{ name, fsmStage, status }], success: true }` — never throws
- Register as `'studio.list_plans'` in the studioTools registry

Phase 2 — Add `studio.get_events` tool:
- Add `async function getEvents(params)` — extracts `feature?` and `limit?` (default 20, cap 50)
- Reads EVENTS.jsonl via existing `safeRead()`, splits lines, returns last `limit` lines
- Returns `{ events: string, success: true }` — empty string when file absent
- Register as `'studio.get_events'`

Phase 3 — Add `studio.get_failures` tool:
- Add `async function getFailures(params)` — extracts `feature?` and `type: 'review'|'test'|'all'`
- Reads feedback/REVIEW_FAILURES.md and/or feedback/TEST_FAILURES.md via `safeRead()` (3000 char limit each)
- Returns `{ review: string, test: string, success: true }` — empty strings when absent
- Register as `'studio.get_failures'`

Phase 4 — Add `studio.create_plan` tool:
- Add `async function createPlan(params)` — extracts `featureName` and optional `description`
- Check folder existence via `window.pathly.fs.listDirs(plansDir).includes(featureName)` — return `{ success: false, error: 'Plan already exists' }` if so
- Write STATE.json: `{ "state": "PLAN", "feature": featureName, "rigor": "standard" }`
- Write USER_STORIES.md: minimal template with feature name header and one empty story stub
- IMPORTANT: verify that `window.pathly.fs.write` creates parent directories. Read studio/src/main/ipc/fs.ts to check. If it does NOT use `{ recursive: true }` mkdir, add that to the fs.ts handler.
- Returns `{ path: 'pathly/plans/${featureName}', success: true }`
- Register as `'studio.create_plan'`

Phase 5 — Add `studio.navigate_to` tool:
- Before implementing: grep renderer source for `__pathlyNavigate` assignments to find valid panel name strings; add a comment listing them
- Add `async function navigateTo(params)` that calls `window.__pathlyNavigate?.(panel)` using optional chaining
- Returns `{ success: true }` if defined; `{ success: false, error: 'navigate not available' }` otherwise
- Register as `'studio.navigate_to'`

Phase 5a — Add `studio.get_layout` tool:
- Add `async function getLayout()` that returns a STATIC + LIVE manifest:
  Static (hardcoded from known Pathly structure):
  - `panels`: ['monitor', 'plan', 'chat', 'flow', 'terminal']
  - `buttons`: array of { label, dataLabel, panel, action } for all HQ controls
  - BEFORE hardcoding: read studio/src/renderer/src/components/HQ/ to confirm the exact data-label values for: start, go, pause, ff, help, team, end — do not guess
  Live (read from Zustand stores at call time):
  - `currentPanel`: useUiStore.getState().activePanel
  - `activeFeature`: useProjectStore.getState().activeTopic
  - `fsmStage`: from runnerStore or 'unknown' — check store directory for runnerStore or RunnerStatus
  - `runnerStatus`: from runnerStore.status
  - `terminalTabs`: from useTerminalStore.getState() — map open tabs to { id, label, kind }
- Returns `{ layout: { panels, buttons, currentPanel, activeFeature, fsmStage, runnerStatus, terminalTabs }, success: true }`
- Register as both `'studio.get_layout'` and `'get_layout'`

Architectural rules to observe:
- Read CLAUDE.md and studio/CLAUDE.md before implementing — no inline styles, IPC pattern, component size limits
- Stay within studioAnalyzer.ts only. Do NOT touch preload, global.d.ts, or brightskyClient.ts.
- All new tool functions follow the same shape as existing `getFsmState`, `getFeaturePlan` functions in the file

Do NOT touch: fsm.ts, preload/index.ts, global.d.ts, brightskyClient.ts, or any BrightSky backend files.
Verify: npm run typecheck from repo root (C:\Users\Yafit\pathly-adapters) — must exit 0 with no new errors
After done, update pathly/plans/brightsky-agent-upgrade/PROGRESS.md phases 0–5 and 5a to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** `studioAnalyzer.ts` has 6 new tool functions + 7 new entries in `studioTools` registry. `npm run typecheck` passes.
**Files touched:** `studio/src/renderer/src/lib/studioAnalyzer.ts` (possibly `studio/src/main/ipc/fs.ts` if mkdir fix needed)

---

## Conversation 2: Studio — run_skill IPC + reasoning box (Phases 6–8)

**Stories delivered:** S-07, S-08

**Prompt to paste:**
```
Read pathly/plans/brightsky-agent-upgrade/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement BrightSky Agent Upgrade — Conversation 2 (Phases 6–8) from pathly/plans/brightsky-agent-upgrade/IMPLEMENTATION_PLAN.md.

Conversation 1 is complete. This conversation spans 5 files.

**Before editing anything:** glob/read the live repo to confirm all 5 files exist:
- studio/src/main/ipc/fsm.ts
- studio/src/main/preload/index.ts
- studio/src/renderer/src/types/global.d.ts
- studio/src/renderer/src/lib/studioAnalyzer.ts
- studio/src/renderer/src/lib/brightskyClient.ts

**Scope:**

Phase 6 — New `fsm:runSkill` IPC handler (fsm.ts):
- FIRST: read the FlowControlBar component (search renderer/src/components for FlowControlBar) to find the POST /runner/start request body shape
- Add `ipcMain.handle('fsm:runSkill', async (_event, topic, skill, projectPath))` to `registerFsmHandlers()` in `studio/src/main/ipc/fsm.ts`
- POST to `${FSM_BASE}/runner/start` with the body format from FlowControlBar
- Return `{ success: boolean, runId?: string, error?: string }`

Phase 7 — Expose + type + studioAnalyzer handler:
- In `preload/index.ts`: add `runSkill: (topic, skill, projectPath) => ipcRenderer.invoke('fsm:runSkill', topic, skill, projectPath)` to the fsm object
- In `global.d.ts`: add `runSkill: (topic: string, skill: string, projectPath: string) => Promise<{ success: boolean; runId?: string; error?: string }>` to the `fsm` type in both the contextBridge declaration and the Window interface
- In `studioAnalyzer.ts`: add `async function runSkill(params)` that extracts `{ feature, skill }`, gets `projectPath` from `useProjectStore`, calls `window.pathly.fsm.runSkill(feature, skill, projectPath)` — register as `'studio.run_skill'`

Phase 8 — Reasoning box: stream_end calls splitThinkingContent (brightskyClient.ts):
- FIRST: find where `splitThinkingContent` is imported in useHQ.tsx — note the import path, likely `../lib/thinkingParser` relative to useHQ.tsx location
- In `brightskyClient.ts`: add import for `splitThinkingContent` using the correct path relative to brightskyClient.ts
- In the `stream_end` handler: call `splitThinkingContent(this.streamContent)`, then update message with `{ content: content || this.streamContent, thinking, status: 'done' }` before clearing streamContent
- In the `stream_chunk` handler's `isDone === true` branch: same — call `splitThinkingContent(this.streamContent)` and update with `{ content, thinking, status: 'done' }`
- Do NOT change mid-stream updates (the plain `updateLastMessage({ content: this.streamContent })` on non-done chunks stays as is)
- Verify the `Message` interface in chatStore.ts already has a `thinking?: string` field — if not, add it

Architectural rules:
- Read CLAUDE.md and studio/CLAUDE.md before implementing
- IPC pattern: every new channel needs registration in ipcMain, preload, AND global.d.ts — all three

Do NOT touch: studioAnalyzer.ts (except adding run_skill handler), any BrightSky backend files.
Verify: npm run typecheck from repo root — both tsconfig.web.json and tsconfig.node.json must pass (npm run typecheck runs both)
After done, update pathly/plans/brightsky-agent-upgrade/PROGRESS.md phases 6–8 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** `window.pathly.fsm.runSkill` is callable; BrightSky `<think>` content shows in ThinkingBlock; typecheck passes.
**Files touched:** `studio/src/main/ipc/fsm.ts`, `studio/src/main/preload/index.ts`, `studio/src/renderer/src/types/global.d.ts`, `studio/src/renderer/src/lib/studioAnalyzer.ts`, `studio/src/renderer/src/lib/brightskyClient.ts`

---

## Conversation 3: BrightSky backend — register 7 tools + Pathly agent routing (Phases 9–10, 10a)

**Stories delivered:** S-09, S-10

**Prompt to paste:**
```
Read pathly/plans/brightsky-agent-upgrade/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement BrightSky Agent Upgrade — Conversation 3 (Phases 9–10, 10a) from pathly/plans/brightsky-agent-upgrade/IMPLEMENTATION_PLAN.md.

This conversation works in the brightsky-ai repo at C:\Users\Yafit\brightsky-ai\backend\

**Before editing anything:** glob/read the live repo to confirm:
- C:\Users\Yafit\brightsky-ai\backend\src\mcp\tools\studio-bridge-tool.ts exists
- C:\Users\Yafit\brightsky-ai\backend\src\mcp\mcp.module.ts exists
- C:\Users\Yafit\brightsky-ai\backend\src\services\unified-ai.service.ts exists
- Run `npx tsc --noEmit` in C:\Users\Yafit\brightsky-ai\backend\ and record any pre-existing errors as baseline

**IMPORTANT MODEL CONTEXT:** BrightSky does NOT use Claude. Its primary model is Gemini 2.5 Flash via gemini.service.ts. The Anthropic SDK is installed but has zero imports anywhere in the codebase. All AI calls go through UnifiedAIService which routes to Gemini, Groq, xAI, or OpenAI.

**Scope:**

Phase 9 — Add 7 StudioBridgeTool subclasses (studio-bridge-tool.ts):
- Read the entire studio-bridge-tool.ts file first — understand the base class and how existing tools are structured
- Add 7 new classes following the same pattern:
  - `ListPlansTool` with `toolName = 'studio.list_plans'`
  - `GetEventsTool` with `toolName = 'studio.get_events'`
  - `GetFailuresTool` with `toolName = 'studio.get_failures'`
  - `CreatePlanTool` with `toolName = 'studio.create_plan'`
  - `NavigateToTool` with `toolName = 'studio.navigate_to'`
  - `RunSkillTool` with `toolName = 'studio.run_skill'`
  - `GetLayoutTool` with `toolName = 'studio.get_layout'` and description: "Returns a static manifest of all Pathly Studio UI elements (panels, buttons with data-labels, actions) plus live state (current panel, active feature, FSM stage, runner status, terminal tabs)"
- Each class passes parameters through to the Studio tool bridge as-is

Phase 10 — Register 7 tools in mcp.module.ts:
- Find the tool provider array near line 365 where existing studio tools are registered
- Add all 7 new classes including GetLayoutTool
- Follow the exact same provider registration pattern

Phase 10a — Pathly agent routing in unified-ai.service.ts:
- Read unified-ai.service.ts — find the provider selection/routing logic (near lines 345-387)
- Trace how messageType flows from WsMessageHandler into UnifiedAIService (look for customInstructions, metadata, or session context)
- Add a guard at the top of provider selection: when messageType === 'pathly_chat', force provider = 'gemini' and skip normal routing. Add comment: "// Pathly messages always use Gemini for thinkingConfig support"
- Find where available tools are assembled for a session — add 'web_search', 'youtube_search', 'youtube_transcript' to the tool set when messageType === 'pathly_chat'
- Non-Pathly messages: routing and tool sets unchanged

Architectural rules:
- Stay in these three files only
- Do NOT touch gemini.service.ts, reasoning-timer.service.ts, pathly-router.service.ts, or any Studio files

Do NOT touch: gemini.service.ts, reasoning-timer.service.ts, or any Studio (pathly-adapters) files.
Verify: npx tsc --noEmit in C:\Users\Yafit\brightsky-ai\backend\ — must exit 0 with no new errors
After done, update pathly/plans/brightsky-agent-upgrade/PROGRESS.md phases 9–10, 10a to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** 7 new tool classes; all 7 registered; Gemini pinned + search tools enabled for pathly_chat; TypeScript passes.
**Files touched:** `backend/src/mcp/tools/studio-bridge-tool.ts`, `backend/src/mcp/mcp.module.ts`, `backend/src/services/unified-ai.service.ts`

---

## Conversation 4: BrightSky backend — Gemini thinking stream (Phases 11–12)

**Stories delivered:** S-11

**Prompt to paste:**
```
Read pathly/plans/brightsky-agent-upgrade/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement BrightSky Agent Upgrade — Conversation 4 (Phases 11–12) from pathly/plans/brightsky-agent-upgrade/IMPLEMENTATION_PLAN.md.

This conversation works in the brightsky-ai repo at C:\Users\Yafit\brightsky-ai\backend\

**CRITICAL MODEL CONTEXT:** BrightSky does NOT use Claude/Anthropic. Its primary model is Gemini 2.5 Flash via backend/src/services/gemini.service.ts. The Anthropic SDK is in package.json but has zero imports. Do NOT search for or modify any Anthropic/Claude API calls — they don't exist. All thinking work is in gemini.service.ts.

**Before editing anything:**
- Read backend/src/services/gemini.service.ts — find generateContentStream() (near line 1353)
- Trace how messageType flows from WsMessageHandler → UnifiedAIService → gemini.service.ts (Conversation 3 added Gemini pinning for pathly_chat — verify it is in place)
- Read reasoning-timer.service.ts to understand how synthetic thinking steps are triggered
- Run npx tsc --noEmit in backend/ and record baseline

**Scope:**

Phase 11 — Add Gemini thinkingConfig for pathly_chat (gemini.service.ts):
- In generateContentStream(): add conditional — if called in pathlyMode (flag passed from UnifiedAIService when messageType === 'pathly_chat'), add to request:
  `generationConfig: { thinkingConfig: { thinkingBudget: 8000 } }`
- Add `pathlyMode?: boolean` parameter to the function signature (or pass via options object — follow existing pattern)
- Capture Gemini thinking content parts from the stream — Gemini 2.5 Flash returns thinking as content parts with a `thought: true` property or a dedicated thinking part type. Read the Gemini SDK streaming response types to confirm the exact field name
- Collect thinking text and return/pass it to the stream handler for Phase 12

Phase 12 — Stream thinking as <think> tags; guard synthetic steps (reasoning-timer.service.ts):
- In reasoning-timer.service.ts: add a guard — if messageType === 'pathly_chat', return immediately and skip all synthetic thinking step generation
- In the gemini.service.ts streaming handler: when a thinking part is captured, emit a stream_chunk WebSocket message with content `<think>${thinkingText}</think>` BEFORE the first text content chunk. Use the same sendStreamChunk() method or equivalent used by response-delivery.service.ts

Architectural rules:
- thinkingConfig must NOT fire for non-Pathly Gemini calls — add an explicit pathlyMode guard
- The <think> chunk MUST be sent before any text chunks — ordering matters for ThinkingBlock to appear
- Do NOT change non-Pathly message behavior in any service

Do NOT touch: unified-ai.service.ts, studio-bridge-tool.ts, mcp.module.ts, or any Studio (pathly-adapters) files.
Verify: npx tsc --noEmit in C:\Users\Yafit\brightsky-ai\backend\ — must exit 0 with no new errors
After done, update pathly/plans/brightsky-agent-upgrade/PROGRESS.md phases 11–12 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Pathly messages use Gemini thinkingConfig; thinking parts stream as `<think>` tags before visible text; synthetic steps suppressed for Pathly; TypeScript passes.
**Files touched:** `backend/src/services/gemini.service.ts`, `backend/src/chat/gateways/session/services/reasoning-timer.service.ts`
