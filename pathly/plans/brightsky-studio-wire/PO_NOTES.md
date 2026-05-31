# PO Notes — brightsky-studio-wire

## Problem

Pathly Studio connects to the Brightsky backend at the transport level (WebSocket + auth working)
but sends only a bare text message with no workspace context. The backend falls back to generic
chat with no awareness of the active feature, pipeline stage, or plan files. The AI cannot
reason about what the user is building or drive any Studio UI action.

## Users

Pathly Studio users running the dev pipeline — they want the AI in the chat panel to:
- Know what feature they are working on and what stage the pipeline is in
- Answer questions grounded in the actual plan files (USER_STORIES.md, IMPLEMENTATION_PLAN.md)
- Drive Studio UI actions on their behalf (fill wizard inputs, click buttons, advance pipeline)
- Show visible feedback while the backend is thinking

## MVP Scope (Phase 1–3 from BUILDING_BLOCKS.md)

**Phase 1 — Frontend only, no backend changes needed:**
- Handle `typing_metadata` WebSocket messages → show "Analyzing…" thinking indicator
- Attach Pathly context (FSM stage, feature name, plan summary) to every outbound message
- Send capability handshake on connect
- Add reconnect with exponential backoff

**Phase 2 — Backend PathlyModule:**
- PathlyContextBuilder service — builds workspace-aware system prompt from appContext
- Route `source: pathly-studio` messages to PathlyRouterService in UnifiedChatGateway
- Backend answers become plan-aware ("you are in BUILD stage, next story is S-04")

**Phase 3 — Studio Analyzer + tool bridge:**
- Handle `tool_call` WebSocket messages → route to StudioAnalyzer tool registry
- StudioAnalyzer tools: get_fsm_state, get_feature_plan, get_studio_schema, automation:executeStep
- PlaywrightExecutor fix: React-compatible fill, implement navigate action
- data-label attributes on all interactive wizard and form components
- Backend ToolRegistry: register StudioAnalyzer bridge tools

## Out of Scope (MVP)

- Cross-surface shared sessions (Chrome extension + Studio same session)
- Source citation rendering (Phase 2 nice-to-have)
- Session history persistence across app restarts

## Constraints

- Electron renderer only (no Node.js APIs in renderer — must go via IPC)
- `window.pathly.automation.executeStep` already exposed in preload — use it
- `window.pathly.fsm.state()` and `window.pathly.fs.read()` already exposed — use them
- React controlled inputs require native setter trick for fill actions
- Backend is NestJS — add PathlyModule as new module, do not modify existing modules
- Token budget for plan file injection: ≤ 4000 tokens total

## Success Criteria

- Brightsky chat in Studio shows "Analyzing your plan…" while backend is thinking
- Every outbound message carries activeFeature, fsmStage, nextUncompletedStory
- Capability handshake sent after session_created
- Backend answers reference actual plan content not generic knowledge
- tool_call round-trip works: backend calls get_fsm_state → Studio reads STATE.json → sends result back
- AI can click wizard button and fill feature name input via automation:executeStep tool_call
- All wizard/form inputs have data-label attributes for Tier 1 resolution
- Reconnect after disconnect without app restart
