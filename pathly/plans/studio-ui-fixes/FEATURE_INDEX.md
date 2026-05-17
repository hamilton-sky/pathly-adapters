# studio-ui-fixes — Feature Index

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| FEATURE_INDEX.md | planner | builder, all | Entry point: all plan files + codebase touchpoints |
| USER_STORIES.md | planner | builder, tester | 4 stories with acceptance criteria |
| IMPLEMENTATION_PLAN.md | planner | builder | 11 phases across 3 conversations |
| PROGRESS.md | planner | orchestrator, builder | Tracking table |
| CONVERSATION_PROMPTS.md | planner | builder | 3 verbatim builder prompts |
| HAPPY_FLOW.md | planner | builder, tester | Ideal user journey |
| EDGE_CASES.md | planner | builder, tester | Edge cases and guard conditions |
| ARCHITECTURE_PROPOSAL.md | planner | builder | Design decisions |
| FLOW_DIAGRAM.md | planner | builder | ASCII flow diagram |

## Codebase touchpoints

| File | Conv | Change |
|---|---|---|
| `studio/src/renderer/src/types/index.ts` | 1, 3 | Conv 1: add `from?`, `to?`, `reason?` to FsmEvent; make `ts?` optional. Conv 3: add `'debug' \| 'explore'` to PathlyItemType |
| `studio/src/renderer/src/components/Monitor/EventLog.tsx` | 1 | Replace `ev.detail` with derived `eventDetail(ev)` helper; fix `formatTime` to handle missing `ts` |
| `studio/src/renderer/src/components/Monitor/index.tsx` | 1, 2 | Conv 1: remove `.slice(-50)` from EVENTS parser, handle missing `ts`. Conv 2: after loading fsmState, read flow YAML and call `setPipelineStates` |
| `studio/src/renderer/src/store/projectStore.ts` | 2 | Add `pipelineStates: string[]` field and `setPipelineStates` action |
| `studio/src/renderer/src/components/Monitor/FsmView.tsx` | 2 | Replace hardcoded `PIPELINE` constant with `pipelineStates` from store |
| `studio/src/renderer/src/hooks/useProjectFiles.ts` | 3 | Add DEBUGS and EXPLORATIONS entries (subdir-based, same pattern as Templates) |
| `studio/src/renderer/src/components/Sidebar.tsx` | 3 | Add DEBUGS and EXPLORATIONS to SECTIONS; render using the existing subdir branch |
| `studio/src/renderer/src/hooks/usePlanConversations.ts` | 3 | Rewrite parser to scope to the Conversation Breakdown table only |
| `studio/src/renderer/src/components/PlanBoard.tsx` | 3 | Same parser fix; replace per-conv event filtering with a flat recent-events section |

## Conversation map

| Conv | Phases | Stories | Status | Verify |
|---|---|---|---|---|
| 1 | 1.1–1.3 | S1 | TODO | `cd studio && npm run typecheck` → zero errors |
| 2 | 2.1–2.3 | S2 | TODO | `cd studio && npm run typecheck` → zero errors |
| 3 | 3.1–3.5 | S3, S4 | TODO | `cd studio && npm run typecheck` → zero errors |

## Optional plan files

| File | Included |
|---|---|
| HAPPY_FLOW.md | yes |
| EDGE_CASES.md | yes |
| ARCHITECTURE_PROPOSAL.md | yes |
| FLOW_DIAGRAM.md | yes |

## MCP scope note

`studio/src/main/ipc/mcp.ts` is fully stubbed — `mcp:ping` always returns `false`.
MCP event subscription is **out of scope** for this plan; it depends on `mcp-fsm-driver` completing first.
