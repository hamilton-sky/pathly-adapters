# studio-visual-flow-builder - Progress

## Status: NOT STARTED

## Story Status

| Story | Title | Delivered by | Status |
|-------|-------|--------------|--------|
| S1 | Existing YAML renders as a connected graph | Conv 1 | TODO |
| S2 | Visual graph changes update canonical YAML data | Conv 1 | TODO |
| S3 | Users can drag skills and agents from the library | Conv 2 | TODO |
| S4 | Clicking a node opens a real node inspector | Conv 3 | TODO |
| S5 | Clicking an edge opens transition configuration | Conv 3 | TODO |
| S6 | YAML preview remains synchronized and safe | Conv 4 | TODO |
| S7 | Users can export approved flows | Conv 4 | TODO |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|------|--------|---------|--------|--------|
| 1 | 1-3 | S1, S2 | TODO | `cd studio; npm run typecheck` |
| 2 | 4-6 | S3 | TODO | `cd studio; npm run typecheck` |
| 3 | 7-9 | S4, S5 | TODO | `cd studio; npm run typecheck` |
| 4 | 10-12 | S6, S7 | TODO | `cd studio; npm run typecheck` |

See **CONVERSATION_PROMPTS.md** for exact prompts to paste in each conversation.

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|------|-------|------|-------------|-----------|--------|
| 1 | Restore connected graph rendering | `studio/src/renderer/src/components/FlowEditor/VisualView/StateNode.tsx` | Add React Flow handles | Existing YAML transitions attach visually to state nodes | TODO |
| 1 | Resync graph state | `studio/src/renderer/src/components/FlowEditor/hooks/useFlowGraph.ts` | Rebuild graph when selected flow changes | Switching files shows the selected file's graph | TODO |
| 1 | Keep visual graph edits canonical | `studio/src/renderer/src/components/FlowEditor/utils/flowToGraph.ts` | Stabilize conversion and labels | Canvas connects update flow data and YAML output | TODO |
| 2 | Add draggable library metadata | `studio/src/renderer/src/types/index.ts` | Add drag/drop item types | Drag/drop handlers can identify item type and path | TODO |
| 2 | Wire sidebar drag/drop | `studio/src/renderer/src/components/Sidebar.tsx` | Add drag start data to skills/agents | Items drag without breaking click behavior | TODO |
| 2 | Handle canvas drops | `studio/src/renderer/src/components/FlowEditor/VisualView/index.tsx` | Drop items onto nodes or empty canvas | Drops update flow data and dirty state | TODO |
| 3 | Node inspector | `studio/src/renderer/src/components/FlowEditor/VisualView/NodePanel.tsx` | Add node config sections | Node click opens useful editable inspector | TODO |
| 3 | Edge inspector | `studio/src/renderer/src/components/FlowEditor/VisualView/EdgePanel.tsx` | Add transition config sections | Edge click opens useful editable inspector | TODO |
| 3 | Validation state | `studio/src/renderer/src/components/FlowEditor/VisualView/index.tsx` | Show graph validation issues | Invalid flow conditions are visible before save/export | TODO |
| 4 | YAML preview sync | `studio/src/renderer/src/components/FlowEditor/YamlView/index.tsx` | Preserve last valid graph and parse errors | Invalid YAML cannot destroy valid graph state | TODO |
| 4 | Export target UI | `studio/src/renderer/src/components/FlowEditor/VisualView/index.tsx` | Add export controls | Valid flow can be exported to explicit targets | TODO |
| 4 | Export helpers | `studio/src/renderer/src/services/pathlyApi.ts` | Add minimal export file helper if needed | Export avoids duplicate filesystem IPC logic | TODO |

## Prerequisites

- Existing dirty worktree state must be reviewed before implementation.
- Existing Studio typecheck drift should be separated from new failures if present.

## Blocked By

- Nothing.
