# Studio AI Chat — Progress

## Status: NOT STARTED

## Story Status

| Story | Title | Delivered by | Status |
|-------|-------|--------------|--------|
| S0.1 | Terminal dock is compact and IDE-style | Conv 0 | TODO |
| S0.2 | Sessions and launchers have clear visual hierarchy | Conv 0 | TODO |
| S0.3 | ALLOWED_SHELLS accepts claude and codex | Conv 0 | TODO |
| S1.1 | phi4-mini explainer responds via SSE | Conv 1 | TODO |
| S1.2 | System prompt includes active Pathly context | Conv 1 | TODO |
| S2.1 | Collapsible Conductor panel | Conv 2 | TODO |
| S2.2 | phi4-mini explanation streams in real-time | Conv 2 | TODO |
| S2.3 | Skills panel shows all skills as chips | Conv 2 | TODO |
| S2.4 | Empty state guides user to start a new flow | Conv 2 | TODO |
| S3.1 | MatchCard shows matched skill + confidence | Conv 3 | TODO |
| S3.2 | Run writes skill command to terminal tab | Conv 3 | TODO |
| S4.1 | Context includes FSM stage + screen state | Conv 4 | TODO |
| S4.2 | Skills list always in context | Conv 4 | TODO |
| S5.1 | MiniLM loads at startup | Conv 5 | TODO |
| S5.2 | Embedding matches intent to Pathly skill | Conv 5 | TODO |
| S5.3 | Low-confidence state guides user to correct skill | Conv 5 | TODO |
| S6.1 | Components self-register with page analyzer | Conv 6 | TODO |
| S6.2 | AI receives live page element map | Conv 6 | TODO |
| S6.3 | Page context updates on UI changes | Conv 6 | TODO |
| S7.1 | AI can click a button | Conv 7 | TODO |
| S7.2 | AI can fill a text input | Conv 7 | TODO |
| S7.3 | AI can select a dropdown option | Conv 7 | TODO |
| S8.1 | Staged mode with per-step approval | Conv 8 | TODO |
| S8.2 | Auto mode executes full plan | Conv 8 | TODO |
| S8.3 | Auto mode blocked on low confidence | Conv 8 | TODO |
| S8.4 | Full flow creation from plain-English description | Conv 8 | TODO |
| S9.1 | Model selector shows all models with specs | Conv 9 | TODO |
| S9.2 | Model download and cache via toggle | Conv 9 | TODO |
| S9.3 | Selected model used for all AI responses | Conv 9 | TODO |
| S9.4 | Model selection persists across restarts | Conv 9 | TODO |

## Conversation Breakdown

| Conv | Phases | Track | Stories | Status | Verify |
|------|--------|-------|---------|--------|--------|
| 0 | 0a–0c | Core | S0.1, S0.2, S0.3 | TODO | `cd studio && npm run typecheck` + visual check in Studio |
| 1 | 1–3 | Core | S1.1, S1.2 | TODO | `curl -X POST http://127.0.0.1:8765/chat -d '{"message":"explain /pathly build","matchedSkill":"build","history":[]}'` |
| 2 | 4–8 | Core | S2.1, S2.2, S2.3, S2.4 | TODO | `cd studio && npm run typecheck` |
| 3 | 9–11 | Core | S3.1, S3.2 | TODO | `cd studio && npm run typecheck` |
| 4 | 12–14 | Core | S4.1, S4.2 | TODO | `cd studio && npm run typecheck` |
| 5 | 15–18 | Core | S5.1, S5.2, S5.3 | TODO | `cd studio && npm run typecheck` |
| 6 | 19–21 | Track A | S6.1, S6.2, S6.3 | TODO | `cd studio && npm run typecheck` + verify registry in React DevTools |
| 7 | 22–23 | Track A | S7.1, S7.2, S7.3 | TODO | `cd studio && npm run typecheck` + manual click/fill test in Studio |
| 8 | 24–26 | Track A | S8.1, S8.2, S8.3, S8.4 | TODO | E2E: type "create a test flow" → approve steps → flow appears in Studio |
| 9 | 27–29 | Track B | S9.1, S9.2, S9.3, S9.4 | TODO | Select Phi-4 Mini → download → send message → response streams from WebLLM |

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|------|-------|------|-------------|-----------|--------|
| 0 | 0a | `studio/src/main/ipc/terminal.ts` | Add claude+codex to ALLOWED_SHELLS | Terminal tabs launch without "Shell not allowed" | TODO |
| 0 | 0b | `Terminal/index.tsx` + CSS | Compact dock: 180px default, 72px empty, inline launchers | No blank dead zone, launch buttons visible | TODO |
| 0 | 0c | `Terminal/PaneTabBar.tsx` + CSS | Sessions vs launchers hierarchy, active tab styling | Clear visual separation, active tab legible | TODO |
| 1 | 1 | `src/pathly_orchestrator/http_server.py` | Add POST /chat SSE skeleton + GET /status | curl returns 200, /status returns stage | TODO |
| 1 | 2 | `src/pathly_orchestrator/chat_agent.py` | phi4-mini explainer agent | Streams 2-3 sentence explanation | TODO |
| 1 | 3 | `src/pathly_orchestrator/chat_tools.py` | get_fsm_state, read_plan_summary | AI references FSM stage by name | TODO |
| 2 | 4 | `studio/src/renderer/src/store/chatStore.ts` | Zustand store — messages + match state | No TS errors | TODO |
| 2 | 5 | `studio/src/renderer/src/store/uiStore.ts` | Add chatOpen, skillsPanelOpen | State persists across remounts | TODO |
| 2 | 6 | `ChatPanel/ConductorHeader.tsx` | Header + CLI pills | Pills show active/idle state | TODO |
| 2 | 7 | `ChatPanel/SkillsPanel.tsx` | Skill chips grid + collapse | All 14 chips render, chip click works | TODO |
| 2 | 8 | `MessageList.tsx` + `ChatInput.tsx` | Messages + input bar | Streaming works, model pills visible | TODO |
| 3 | 9 | `ChatPanel/MatchCard.tsx` | Match result card | Green/amber states, Run/Not this work | TODO |
| 3 | 10 | `ChatPanel/OutputSnippet.tsx` | Live PTY output reader | Shows last 5 lines in real-time | TODO |
| 3 | 11 | `studio/src/main/ipc/chat.ts` + `index.ts` | IPC terminal write handler | PTY receives command | TODO |
| 4 | 12 | `studio/src/renderer/src/lib/pathlyContext.ts` | Context builder | Returns { fsmStage, featureName, screenElements, skills } | TODO |
| 4 | 13 | `studio/src/renderer/src/lib/pageAnalyzer/` | DOM analyzer (from BrightSky) | Compiles without errors | TODO |
| 4 | 14 | `ChatPanel/index.tsx` | Inject context into every message | AI references FSM stage | TODO |
| 5 | 15 | `studio/src/renderer/src/data/skills.json` | 14 skills with name+command+description | File valid JSON, all skills present | TODO |
| 5 | 16 | `studio/src/renderer/src/lib/skillsManifest.ts` | Typed loader for skills.json | No TS errors | TODO |
| 5 | 17 | `studio/src/renderer/src/lib/embedRouter.ts` | MiniLM wrapper + matchIntent() | Returns top-3 matches with scores | TODO |
| 5 | 18 | `ChatPanel/index.tsx` + `chatStore.ts` | Wire embedding into send flow | MatchCard renders < 50ms after send | TODO |
| 6 | 19 | `hooks/usePageAnalyzer.ts` | Self-registration hook | Hook compiles, elements appear in store | TODO |
| 6 | 20 | `store/pageAnalyzerStore.ts` + `lib/pageAnalyzer/index.ts` | Element registry + getPageContext() | getPageContext() returns live JSON | TODO |
| 6 | 21 | `lib/pathlyContext.ts` | Inject page context into chat | AI references screen elements by label | TODO |
| 7 | 22 | `main/ipc/uiActions.ts` + `main/index.ts` | IPC action handler | ipcRenderer.invoke('ui:execute-action') works | TODO |
| 7 | 23 | `lib/actionExecutor.ts` + `App.tsx` | Renderer action executor | Click/fill/select executes on real DOM | TODO |
| 8 | 24 | `store/automationStore.ts` | Step queue state | No TS errors | TODO |
| 8 | 25 | `ChatPanel/StepQueue.tsx` + `AutomationCard.tsx` | Staged/auto UI components | Staged approve/skip works visually | TODO |
| 8 | 26 | `ChatPanel/index.tsx` + `chat_agent.py` | Wire AI → action plan → execution | Full flow creation E2E works | TODO |
| 9 | 27 | `data/models.ts` + `lib/webLLMEngine.ts` | WebLLM models data + engine | Phi-4 Mini loads and streams response | TODO |
| 9 | 28 | `store/modelStore.ts` + `ChatPanel/ModelSelector.tsx` | Model selector UI | Download, cache, selection all work | TODO |
| 9 | 29 | `ChatPanel/index.tsx` + `chat_agent.py` | Wire WebLLM into chat flow | Responses stream from local model | TODO |

## Prerequisites
- [ ] FSM server running before testing Conv 1
- [ ] MiniLM auto-downloads on first launch (~22MB, transformers.js)
- [ ] WebLLM models download on first cache (Phi-4 Mini ~2GB — Conv 9)
- [ ] Ollama optional (legacy backend only, not required for Conv 9+)

## Blocked By
- Nothing
