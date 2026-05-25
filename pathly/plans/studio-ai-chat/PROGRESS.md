# Studio AI Chat — Progress

## Status: NOT STARTED

## Story Status

| Story | Title | Delivered by | Status |
|-------|-------|--------------|--------|
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

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|------|--------|---------|--------|--------|
| 1 | 1–3 | S1.1, S1.2 | TODO | `curl -X POST http://127.0.0.1:8765/chat -d '{"message":"explain /pathly build","matchedSkill":"build","history":[]}'` |
| 2 | 4–8 | S2.1, S2.2, S2.3 | TODO | `cd studio && npm run typecheck` |
| 3 | 9–11 | S3.1, S3.2 | TODO | `cd studio && npm run typecheck` |
| 4 | 12–14 | S4.1, S4.2 | TODO | `cd studio && npm run typecheck` |
| 5 | 15–18 | S5.1, S5.2, S5.3 | TODO | `cd studio && npm run typecheck` |

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|------|-------|------|-------------|-----------|--------|
| 1 | 1 | `src/pathly_orchestrator/http_server.py` | Add POST /chat SSE skeleton | curl returns 200 | TODO |
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

## Prerequisites
- [ ] Ollama installed: `winget install Ollama.Ollama`
- [ ] Model pulled: `ollama pull phi4-mini`
- [ ] FSM server running before testing Conv 1

## Blocked By
- Nothing
