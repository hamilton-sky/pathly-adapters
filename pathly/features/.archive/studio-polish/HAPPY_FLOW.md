---
name: Happy Flow
---
# studio-polish — Happy Flow

## Opening a flow file
1. User clicks a `.flow.yaml` file in the sidebar
2. FlowEditor shows shimmer skeleton (4 lines, 1.4s animation)
3. `useFlowFile` reads the file via IPC → parses YAML
4. Skeleton disappears; visual canvas or YAML tab renders with flow content
5. `loading` is false; no error state

## Saving in FlowWizard
1. User completes all 5 wizard steps
2. Clicks "Save" button → button becomes disabled with CSS spinner
3. `writeFile` IPC completes → button re-enables
4. FlowWizard closes (or shows success state)

## YAML syntax error
1. User switches to YAML tab, introduces a typo
2. Switches back to Visual tab
3. js-yaml throws YAMLException with `mark.line = 13`
4. Error banner shows: "YAML parse error on line 14: unexpected token"
5. User can switch back to YAML tab to fix it

## Navigating away from a dirty file
1. User edits a flow in Visual view → `dirtyItems` has the path
2. User clicks a different file in the sidebar
3. Confirm dialog appears: "You have unsaved changes. Discard and continue?"
4. User clicks "Discard changes" → current file is deselected, new file opens
5. If user clicks "Cancel" → stays on current file, no change

## Running the test suite
1. Developer runs `cd studio && npm test`
2. vitest finds useFlowFile.test.ts and validateFlow.test.ts
3. All 8 tests pass in < 5 seconds
