# studio-visual-flow-builder - Progress

## Status: IN PROGRESS

## Story Status

| Story | Title | Delivered by | Status |
|-------|-------|--------------|--------|
| S1 | Existing YAML renders as a connected graph | Conv 1 | DONE |
| S2 | Visual graph changes update canonical YAML data | Conv 1 | DONE |
| S3 | Users can drag skills and agents from the library | Conv 2 | DONE |
| S4 | Clicking a node opens a real node inspector | Conv 3 | DONE |
| S5 | Clicking an edge opens transition configuration | Conv 3 | DONE |
| S6 | YAML preview remains synchronized and safe | Conv 4 | TODO |
| S7 | Users can export approved flows | Conv 4 | TODO |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|------|--------|---------|--------|--------|
| 1 | 1-3 | S1, S2 | DONE | `cd studio; npm run typecheck` |
| 2 | 4-7 | S3, S8 | DONE | `cd studio; npm run typecheck` |
| 3 | 8-11 | S4, S5 | DONE | `cd studio; npm run typecheck` |
| 4 | 12-14 | S6, S7 | TODO | `cd studio; npm run typecheck` |

See **CONVERSATION_PROMPTS.md** for exact prompts to paste in each conversation.

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|------|-------|------|-------------|-----------|--------|
| 1 | 1 | `studio/src/renderer/src/components/FlowEditor/VisualView/StateNode.tsx` | Add React Flow handles | Existing YAML transitions attach visually to state nodes | TODO |
| 1 | 2 | `studio/src/renderer/src/components/FlowEditor/hooks/useFlowGraph.ts` | Rebuild graph when selected flow changes | Switching files shows the selected file's graph | TODO |
| 1 | 3 | `studio/src/renderer/src/components/FlowEditor/utils/flowToGraph.ts` | Stabilize conversion and label edges from the real state-keyed `transition_rules` schema | Canvas connects update flow data and YAML output without losing existing YAML keys | TODO |
| 2 | 4 | `studio/src/renderer/src/types/index.ts` | Add drag/drop item types | Drag/drop handlers can identify item type and path | TODO |
| 2 | 5 | `studio/src/renderer/src/components/Editor/index.tsx` | Open skills/agents/templates in preview by default | Editing library source requires an explicit action | TODO |
| 2 | 6 | `studio/src/renderer/src/components/Sidebar.tsx` | Add drag start data to skills/agents/templates per scope | Items drag without breaking click behavior | TODO |
| 2 | 7 | `studio/src/renderer/src/components/FlowEditor/VisualView/index.tsx` | Drop items onto nodes or empty canvas | Drops update flow data and dirty state | TODO |
| 3 | 8 | `studio/src/renderer/src/components/FlowEditor/VisualView/VisualView.styles.ts` | Convert overlay inspector to docked pane | Inspector opens beside canvas without remounting React Flow | TODO |
| 3 | 9 | `studio/src/renderer/src/components/FlowEditor/VisualView/NodePanel.tsx` | Add node inspector sections and behavior picker | Node click opens useful editable inspector | TODO |
| 3 | 10 | `studio/src/renderer/src/components/FlowEditor/VisualView/EdgePanel.tsx` | Add transition config using state-keyed `transition_rules` | Edge click opens useful editable inspector | TODO |
| 3 | 11 | `studio/src/renderer/src/components/FlowEditor/utils/validateFlow.ts` | Validate graph, rules, actions, and behavior references | Invalid flow conditions are visible before save/export | TODO |
| 4 | 12 | `studio/src/renderer/src/components/FlowEditor/YamlView/index.tsx` | Preserve last valid graph and parse errors | Invalid YAML cannot destroy valid graph state | TODO |
| 4 | 13 | `studio/src/renderer/src/components/FlowEditor/VisualView/index.tsx` | Add export controls | Valid flow can be exported to explicit targets | TODO |
| 4 | 14 | `studio/src/renderer/src/services/pathlyApi.ts` | No-op unless `writeFile` stops creating parent dirs | Export reuses existing filesystem IPC without duplicate logic | TODO |

## Prerequisites

- Existing dirty worktree state must be reviewed before implementation.
- Existing Studio typecheck drift should be separated from new failures if present.
- Builders should run `npm.cmd run typecheck` on Windows if `npm run typecheck` is blocked by PowerShell execution policy.
- Treat `src/pathly_data/core/flows/*.flow.yaml` and `src/pathly_orchestrator/fsm.py` as the schema source of truth for `transition_rules`.

## Blocked By

- Nothing.
