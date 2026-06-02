---
name: User Stories
---
# BrightSky Agent Upgrade — User Stories

## Context

The BrightSky ↔ Pathly Studio integration has a working WebSocket connection, auth, and 3 studio bridge tools (`get_fsm_state`, `get_feature_plan`, `automation.executeStep`). The backend routes Pathly messages through `PathlyRouterService` with an enriched system prompt, but uses synthetic (fake) reasoning steps. The HQ chat panel has a `ThinkingBlock` component that shows a collapsible Reasoning box — but BrightSky messages never populate it because `stream_end` does not call `splitThinkingContent()`.

This feature adds 6 new studio bridge tools (so the BrightSky agent can fully navigate and manage Pathly plans), fixes the reasoning box integration, and replaces synthetic thinking with real Claude extended thinking on the backend.

---

## Stories

### S-01: List active plans
**As a** BrightSky agent, **I want** to call `studio.list_plans`, **so that** I can show the user all active features in their workspace.

**Acceptance Criteria:**
- [ ] `studio.list_plans` returns an array of feature names from `{projectPath}/pathly/plans/`
- [ ] Archived features (in `pathly/plans/.archive/`) are excluded
- [ ] Each entry includes: `name`, `fsmStage` (read from `STATE.json` if present), `status` (active/unknown)
- [ ] Returns `{ plans: [], success: true }` when no plans exist — never throws

**Delivered by:** Phase 1 → Conversation 1

---

### S-02: Read recent FSM events
**As a** BrightSky agent, **I want** to call `studio.get_events`, **so that** I can see recent pipeline activity for context before responding.

**Acceptance Criteria:**
- [ ] `studio.get_events` accepts `{ feature?: string, limit?: number }` — defaults to active feature, last 20 lines
- [ ] Returns last N lines of `{projectPath}/pathly/plans/{feature}/EVENTS.jsonl` as a plain string
- [ ] Returns `{ events: '', success: true }` when file does not exist — never throws
- [ ] `limit` is capped at 50 lines

**Delivered by:** Phase 2 → Conversation 1

---

### S-03: Read review and test failures
**As a** BrightSky agent, **I want** to call `studio.get_failures`, **so that** I can read REVIEW_FAILURES.md or TEST_FAILURES.md and help the user fix them.

**Acceptance Criteria:**
- [ ] `studio.get_failures` accepts `{ feature?: string, type: 'review' | 'test' | 'all' }` — defaults to active feature
- [ ] Returns content of `feedback/REVIEW_FAILURES.md` and/or `feedback/TEST_FAILURES.md`
- [ ] Returns `{ review: '', test: '', success: true }` when feedback folder or files do not exist — never throws
- [ ] Content is trimmed to 3000 chars per file

**Delivered by:** Phase 3 → Conversation 1

---

### S-04: Bootstrap a new plan folder
**As a** BrightSky agent, **I want** to call `studio.create_plan`, **so that** I can scaffold a new feature plan for the user without them leaving the chat.

**Acceptance Criteria:**
- [ ] `studio.create_plan` accepts `{ featureName: string, description?: string }`
- [ ] Creates `{projectPath}/pathly/plans/{featureName}/STATE.json` with `{ "state": "PLAN", "feature": featureName }`
- [ ] Creates `{projectPath}/pathly/plans/{featureName}/USER_STORIES.md` with a minimal template (feature name in header, one empty story stub)
- [ ] Returns `{ path: '...', success: true }` on success
- [ ] Returns `{ success: false, error: 'Plan already exists' }` if folder already exists — does not overwrite

**Delivered by:** Phase 4 → Conversation 1

---

### S-05: Navigate Studio to a panel
**As a** BrightSky agent, **I want** to call `studio.navigate_to`, **so that** I can route the user to the relevant panel (Monitor, Plan, etc.) as part of a response.

**Acceptance Criteria:**
- [ ] `studio.navigate_to` accepts `{ panel: string }` where panel matches a valid `__pathlyNavigate` panel name
- [ ] Calls `window.__pathlyNavigate(panel)` in the renderer
- [ ] Returns `{ success: true }` if `__pathlyNavigate` is defined; `{ success: false, error: 'navigate not available' }` otherwise — never throws

**Delivered by:** Phase 5 → Conversation 1

---

### S-06: Studio layout map
**As a** BrightSky agent, **I want** to call `studio.get_layout`, **so that** I know exactly what panels, buttons, and UI elements exist in Pathly Studio before attempting any automation — without needing to analyze the DOM at runtime.

**Acceptance Criteria:**
- [ ] `studio.get_layout` returns a static manifest: `panels`, `buttons` (each with `label`, `data-label`, `panel`, `action`), `currentPanel`, `activeFeature`, `fsmStage`, `runnerStatus`, `terminalTabs`
- [ ] `buttons` covers all HQ controls: start, go, pause, ff, help, team, end — with their data-label values and human-readable action description
- [ ] Live fields (`currentPanel`, `activeFeature`, `fsmStage`, `runnerStatus`) are read from Zustand stores at call time
- [ ] Returns `{ layout: {...}, success: true }` — never throws

**Delivered by:** Phase 5a → Conversation 1

---

### S-07: Trigger a Pathly skill
**As a** BrightSky agent, **I want** to call `studio.run_skill`, **so that** I can kick off a pipeline stage (plan, build, review) on behalf of the user.

**Acceptance Criteria:**
- [ ] `studio.run_skill` accepts `{ feature: string, skill: 'plan' | 'build' | 'review' | 'test' | 'go' }`
- [ ] A new `fsm:runSkill` IPC handler exists in `studio/src/main/ipc/fsm.ts`
- [ ] The handler POSTs to the FSM `/runner/start` with the correct body (same format as FlowControlBar)
- [ ] `window.pathly.fsm.runSkill` is exposed in `preload/index.ts` and typed in `global.d.ts`
- [ ] Returns `{ success: true, runId }` on FSM acceptance; `{ success: false, error }` on failure

**Delivered by:** Phase 6–7 → Conversation 2

---

### S-08: BrightSky reasoning appears in the Reasoning box
**As a** user, **I want** to see BrightSky's reasoning in the collapsible Reasoning box in HQ, **so that** BrightSky and Conductor feel consistent in how they show their thinking.

**Acceptance Criteria:**
- [ ] When BrightSky sends a `stream_chunk` or `stream_end` message containing `<think>...</think>` content, the thinking text appears in the collapsed `ThinkingBlock` component on that message
- [ ] The visible response content does NOT contain the raw `<think>` tags
- [ ] The Reasoning box collapses 800ms after stream completes (existing ThinkingBlock behavior — no change needed)
- [ ] Messages without `<think>` tags are unaffected — `msg.thinking` remains undefined

**Delivered by:** Phase 8 → Conversation 2

---

### S-09: BrightSky backend registers all 7 new tools
**As the** BrightSky backend, **I want** all 7 new studio bridge tools to be registered as MCP tools, **so that** the Pathly-aware agent can call them during a Pathly chat session.

**Acceptance Criteria:**
- [ ] Seven new `StudioBridgeTool` subclasses exist in `studio-bridge-tool.ts`: `ListPlansTool`, `GetEventsTool`, `GetFailuresTool`, `CreatePlanTool`, `NavigateToTool`, `RunSkillTool`, `GetLayoutTool`
- [ ] All seven are registered in `mcp.module.ts` tool provider array
- [ ] Each tool has a `toolName` matching its Studio-side key: `studio.list_plans`, `studio.get_events`, `studio.get_failures`, `studio.create_plan`, `studio.navigate_to`, `studio.run_skill`, `studio.get_layout`
- [ ] TypeScript builds without errors: `npx tsc --noEmit` in `brightsky-ai/backend/`

**Delivered by:** Phase 9–10 → Conversation 3

---

### S-10: Search and YouTube tools available to the Pathly agent
**As a** BrightSky Pathly agent, **I want** access to `web_search`, `youtube_search`, and `youtube_transcript` tools during Pathly chat sessions, **so that** I can look up documentation, tutorials, and code examples without the user leaving the chat.

**Acceptance Criteria:**
- [ ] For `messageType === 'pathly_chat'`, `UnifiedAIService` pins the provider to Gemini (to ensure thinkingConfig compatibility)
- [ ] `web_search`, `youtube_search`, and `youtube_transcript` tools are included in the Pathly agent's available tool set
- [ ] Non-Pathly messages are unaffected — their provider selection and tool set are unchanged
- [ ] TypeScript builds without errors in `brightsky-ai/backend/`

**Delivered by:** Phase 10a → Conversation 3

---

### S-11: Real Gemini thinking for Pathly messages
**As a** user, **I want** BrightSky to use Gemini's real extended thinking for Pathly chat, **so that** the Reasoning box shows genuine reasoning instead of synthetic loading text.

**Acceptance Criteria:**
- [ ] For messages where `messageType === 'pathly_chat'`, the Gemini API call includes `thinkingConfig: { thinkingBudget: 8000 }`
- [ ] Gemini thinking content parts from the response are streamed as `stream_chunk` messages with content wrapped in `<think>...</think>` tags, sent before the main response text
- [ ] The synthetic `reasoning-timer.service.ts` steps are skipped for Pathly messages (non-Pathly messages are unaffected)
- [ ] TypeScript builds without errors in `brightsky-ai/backend/`

**Delivered by:** Phase 11–12 → Conversation 4
