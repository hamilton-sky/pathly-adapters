# Artifact Map — studio-visual-flow-builder
Date: 2026-05-19 | Branch: master

## Feedback Files (archived)

| File | Conv | Rounds | Outcome |
|------|------|--------|---------|
| REVIEW_FAILURES.md | 4 | 2 | Resolved — FlowExportTarget values, FlowValidationIssue fields, resolveExportPath, FlowValidationScope, dead onAddRule prop |
| TEST_FAILURES.md | — | 1 | Resolved — required-artifacts section, YAML save validateFlow, export modal, ConfigForm preview chips |

## Source Files Changed

| File | Change |
|------|--------|
| `studio/src/renderer/src/types/index.ts` | Added PathlySection, PathlyTreeNode, drag item types, FlowExportTarget, FlowExportRecord, FlowValidationIssue |
| `studio/src/renderer/src/components/FlowEditor/VisualView/StateNode.tsx` | Added React Flow Handles, validation badge |
| `studio/src/renderer/src/components/FlowEditor/hooks/useFlowGraph.ts` | Rebuild on flow identity change, fixed transition_rules shape |
| `studio/src/renderer/src/components/FlowEditor/utils/flowToGraph.ts` | Stable edge IDs, nested transition_rules labels, missing state guard |
| `studio/src/renderer/src/components/FlowEditor/utils/validateFlow.ts` | NEW — pure validation function |
| `studio/src/renderer/src/components/FlowEditor/utils/exportPaths.ts` | NEW — resolveExportPath utility |
| `studio/src/renderer/src/components/FlowEditor/zIndex.ts` | NEW — z-index constants |
| `studio/src/renderer/src/components/FlowEditor/VisualView/VisualView.styles.ts` | Docked inspector pane layout |
| `studio/src/renderer/src/components/FlowEditor/VisualView/index.tsx` | Drop handling, export UI, validation wiring |
| `studio/src/renderer/src/components/FlowEditor/VisualView/NodePanel.tsx` | Full inspector with behavior picker, required artifacts, keyboard trap |
| `studio/src/renderer/src/components/FlowEditor/VisualView/EdgePanel.tsx` | State-keyed transition config, human-readable labels |
| `studio/src/renderer/src/components/FlowEditor/YamlView/index.tsx` | Last-valid preservation, validateFlow on save |
| `studio/src/renderer/src/components/FlowEditor/hooks/useFlowFile.ts` | lastValidFlowDataRef, yamlParseError coordination |
| `studio/src/renderer/src/components/FlowEditor/index.tsx` | Wired yamlValidationIssues to YamlView |
| `studio/src/renderer/src/components/Sidebar.tsx` | Drag start (canvas + reorg), drop target highlight |
| `studio/src/renderer/src/components/Editor/index.tsx` | Preview default for skill/agent/template, Edit source button |
| `studio/src/renderer/src/components/Editor/ConfigForm.tsx` | Read-only chips in compact/preview mode |
