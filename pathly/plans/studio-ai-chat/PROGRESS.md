# Studio AI Chat — Progress

## Status: NOT STARTED

## Story Status

| Story | Title | Delivered by | Status |
|-------|-------|--------------|--------|
| S1.1 | Chat server responds via local Ollama | Conv 1 | TODO |
| S1.2 | System prompt includes active Pathly context | Conv 1 | TODO |
| S2.1 | Collapsible right sidebar chat panel | Conv 2 | TODO |
| S2.2 | Messages stream in real-time | Conv 2 | TODO |
| S3.1 | AI proposes terminal commands with approval | Conv 3 | TODO |
| S3.2 | Terminal write approval is configurable | Conv 3 | TODO |
| S4.1 | PageAnalyzer reads screen and adds to context | Conv 4 | TODO |
| S4.2 | Skills list always in system prompt | Conv 4 | TODO |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|------|--------|---------|--------|--------|
| 1 | 1–3 | S1.1, S1.2 | TODO | `curl -X POST http://127.0.0.1:8765/chat -d '{"message":"what stage?","history":[]}'` |
| 2 | 4–7 | S2.1, S2.2 | TODO | `cd studio && npm run typecheck` |
| 3 | 8–9 | S3.1, S3.2 | TODO | `cd studio && npm run typecheck` |
| 4 | 10–12 | S4.1, S4.2 | TODO | `cd studio && npm run typecheck` |

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|------|-------|------|-------------|-----------|--------|
| 1 | 1 | `src/pathly_orchestrator/http_server.py` | Add POST /chat skeleton | curl returns 200 | TODO |
| 1 | 2 | `src/pathly_orchestrator/chat_agent.py` | ReAct loop + Ollama call | Real streamed response | TODO |
| 1 | 3 | `src/pathly_orchestrator/chat_tools.py` | Pathly tools + context injection | AI knows FSM stage | TODO |
| 2 | 4 | `studio/src/renderer/src/store/chatStore.ts` | Zustand chat store | No TS errors | TODO |
| 2 | 5 | `studio/src/renderer/src/components/ChatPanel/index.tsx` | Collapsible panel container | Collapses/expands | TODO |
| 2 | 6 | `MessageList.tsx` + `ChatInput.tsx` | Message list + input bar | Streaming works | TODO |
| 2 | 7 | `studio/src/renderer/src/App.tsx` | Wire panel into layout | Panel visible in Studio | TODO |
| 3 | 8 | `studio/src/main/ipc/chat.ts` | IPC terminal write handler | PTY receives command | TODO |
| 3 | 9 | `TerminalApproval.tsx` + `chatStore.ts` | Approval flow + auto toggle | Banner appears, Run works | TODO |
| 4 | 10 | `studio/src/renderer/src/lib/pageAnalyzer/` | Copy BrightSky analyzers | No TS compile errors | TODO |
| 4 | 11 | `studio/src/renderer/src/lib/pathlyContext.ts` | Context builder | Returns structured context | TODO |
| 4 | 12 | `ChatPanel/index.tsx` | Inject context per message | AI references screen state | TODO |

## Prerequisites
- [ ] Ollama installed: `winget install Ollama.Ollama`
- [ ] Model pulled: `ollama pull phi4-mini`
- [ ] FSM server running: `pathly-fsm-http`

## Blocked By
- Nothing
