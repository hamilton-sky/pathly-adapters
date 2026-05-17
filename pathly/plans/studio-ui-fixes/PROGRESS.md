# studio-ui-fixes — Progress

## Status: NOT STARTED

## Story Status

| Story | Title | Delivered by | Status |
|---|---|---|---|
| S1 | Event log timestamps + detail | Conv 1 | TODO |
| S2 | Dynamic pipeline states | Conv 2 | TODO |
| S3 | Clean PLAN sidebar conversations | Conv 3 | TODO |
| S4 | Sidebar debugs + explorations | Conv 3 | TODO |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|---|---|---|---|---|
| 1 | 1.1–1.3 | S1 | TODO | `cd studio && npm run typecheck` → zero errors |
| 2 | 2.1–2.3 | S2 | TODO | `cd studio && npm run typecheck` → zero errors |
| 3 | 3.1–3.5 | S3, S4 | TODO | `cd studio && npm run typecheck` → zero errors |

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|---|---|---|---|---|---|
| 1 | 1.1 | `types/index.ts` | Extend FsmEvent with from/to/reason; ts optional | typecheck passes | TODO |
| 1 | 1.2 | `Monitor/index.tsx` | Remove .slice(-50) from EVENTS parsers | all events loaded | TODO |
| 1 | 1.3 | `Monitor/EventLog.tsx` | formatTime handles missing ts; eventDetail helper | "Invalid" gone; from→to shown | TODO |
| 2 | 2.1 | `store/projectStore.ts` | Add pipelineStates + setPipelineStates | store field available | TODO |
| 2 | 2.2 | `Monitor/index.tsx` | Read flow YAML, parse states, call setPipelineStates | store populated on topic select | TODO |
| 2 | 2.3 | `Monitor/FsmView.tsx` | Replace hardcoded PIPELINE with store.pipelineStates | correct states shown | TODO |
| 3 | 3.1 | `types/index.ts` | Add 'debug'\|'explore' to PathlyItemType | typecheck passes | TODO |
| 3 | 3.2 | `hooks/useProjectFiles.ts` | Add DEBUGS + EXPLORATIONS subdir sections | sections populated | TODO |
| 3 | 3.3 | `components/Sidebar.tsx` | Render DEBUGS + EXPLORATIONS sections | sidebar shows them | TODO |
| 3 | 3.4 | `hooks/usePlanConversations.ts` | Scope parser to Conversation Breakdown table | clean conv rows in sidebar | TODO |
| 3 | 3.5 | `components/PlanBoard.tsx` | Same parser fix; flat event list | clean board, no empty event cards | TODO |

## Blocked By
- Nothing

## MCP note
`mcp-fsm-driver` must complete before MCP event subscription can be added. Out of scope here.
