---
name: Progress
---
# BrightSky Agent Upgrade — Progress

## Status: NOT STARTED

## Story Status

| Story | Title | Delivered by | Status |
|-------|-------|--------------|--------|
| S-01 | List active plans | Conv 1 | TODO |
| S-02 | Read recent FSM events | Conv 1 | TODO |
| S-03 | Read review and test failures | Conv 1 | TODO |
| S-04 | Bootstrap a new plan folder | Conv 1 | TODO |
| S-05 | Navigate Studio to a panel | Conv 1 | TODO |
| S-06 | Studio layout map (get_layout) | Conv 1 | TODO |
| S-07 | Trigger a Pathly skill (run_skill) | Conv 2 | TODO |
| S-08 | BrightSky reasoning in Reasoning box | Conv 2 | TODO |
| S-09 | BrightSky backend: 7 new tools registered | Conv 3 | TODO |
| S-10 | Search + YouTube tools for Pathly agent | Conv 3 | TODO |
| S-11 | Real Gemini thinking for Pathly messages | Conv 4 | TODO |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|------|--------|---------|--------|--------|
| 1 | Phase 0–5, 5a | S-01–S-06 | TODO | `npm run typecheck` from repo root |
| 2 | Phase 6–8 | S-07, S-08 | TODO | `npm run typecheck` from repo root |
| 3 | Phase 9–10, 10a | S-09, S-10 | TODO | `npx tsc --noEmit` in `brightsky-ai/backend/` |
| 4 | Phase 11–12 | S-11 | TODO | `npx tsc --noEmit` in `brightsky-ai/backend/` |

See **CONVERSATION_PROMPTS.md** for exact prompts to paste in each conversation.

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|------|-------|------|-------------|-----------|--------|
| 1 | Phase 0 | `studio/src/renderer/src/lib/studioAnalyzer.ts` | Pre-flight: confirm existing tools + typecheck baseline | `npm run typecheck` exits 0, existing tools confirmed | TODO |
| 1 | Phase 1 | `studio/src/renderer/src/lib/studioAnalyzer.ts` | Add `studio.list_plans` tool | Returns `{ plans: [...], success: true }` | TODO |
| 1 | Phase 2 | `studio/src/renderer/src/lib/studioAnalyzer.ts` | Add `studio.get_events` tool | Returns last N lines of EVENTS.jsonl | TODO |
| 1 | Phase 3 | `studio/src/renderer/src/lib/studioAnalyzer.ts` | Add `studio.get_failures` tool | Returns review/test failure content | TODO |
| 1 | Phase 4 | `studio/src/renderer/src/lib/studioAnalyzer.ts` | Add `studio.create_plan` tool | Creates STATE.json + USER_STORIES template | TODO |
| 1 | Phase 5 | `studio/src/renderer/src/lib/studioAnalyzer.ts` | Add `studio.navigate_to` tool | Calls `window.__pathlyNavigate(panel)` | TODO |
| 1 | Phase 5a | `studio/src/renderer/src/lib/studioAnalyzer.ts` | Add `studio.get_layout` tool | Returns static UI manifest + live state | TODO |
| 2 | Phase 6 | `studio/src/main/ipc/fsm.ts` | Add `fsm:runSkill` IPC handler | POSTs to FSM `/runner/start` | TODO |
| 2 | Phase 7 | `preload/index.ts`, `global.d.ts`, `studioAnalyzer.ts` | Expose `fsm.runSkill`, add type, add tool handler | `window.pathly.fsm.runSkill` callable from renderer | TODO |
| 2 | Phase 8 | `studio/src/renderer/src/lib/brightskyClient.ts` | Call `splitThinkingContent` at stream_end | `<think>` tags populate ThinkingBlock | TODO |
| 3 | Phase 9 | `backend/src/mcp/tools/studio-bridge-tool.ts` | Add 7 StudioBridgeTool subclasses (incl. GetLayoutTool) | Seven classes with correct toolNames exist | TODO |
| 3 | Phase 10 | `backend/src/mcp/mcp.module.ts` | Register 7 new tools | All 7 appear in provider array | TODO |
| 3 | Phase 10a | `backend/src/services/unified-ai.service.ts` | Pin Gemini + enable search/YouTube for pathly_chat | Provider forced to Gemini; 3 search tools in tool set | TODO |
| 4 | Phase 11 | `backend/src/services/gemini.service.ts` | Add `thinkingConfig` for pathly_chat Gemini calls | Gemini thinking parts captured for pathly_chat | TODO |
| 4 | Phase 12 | `backend/src/chat/…/reasoning-timer.service.ts` | Stream Gemini thinking as `<think>` tags; guard synthetic steps | Reasoning box shows real Gemini thinking | TODO |

## Prerequisites
- BrightSky WebSocket connection working (smoke test: existing `studio.get_fsm_state` tool call succeeds in a live Studio session)
- `npm run typecheck` baseline recorded at Phase 0
- BrightSky uses Gemini 2.5 Flash as primary model — NOT Claude (Anthropic SDK is installed but unused)

## Blocked By
- Nothing
