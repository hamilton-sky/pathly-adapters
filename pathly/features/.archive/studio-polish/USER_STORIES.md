---
name: User Stories
---
# studio-polish — User Stories

## S1: FlowEditor shows a skeleton while loading

**As a** Studio user opening a flow file,
**I want** to see shimmer placeholder lines instead of a blank panel or plain "Loading…" text,
**so that** the app feels responsive during file reads.

**Acceptance criteria:**
- While `loading === true` in FlowEditor, a skeleton UI with 3–5 shimmer lines is visible
- The skeleton disappears when `loading` becomes false
- The skeleton respects the active theme (uses `var(--bg-surface0)` and `var(--bg-surface1)`)

## S2: FlowWizard Save button shows loading state

**As a** user clicking Save in the FlowWizard,
**I want** the button to become disabled with a spinner while saving,
**so that** I know the save is in progress and can't accidentally double-click.

**Acceptance criteria:**
- While `saving === true`, the Save button is `disabled` and shows a CSS spinner
- The spinner uses `var(--accent)` color
- After save completes (success or error), the button returns to its normal state

## S3: YAML parse errors show the line number

**As a** Studio user switching from YAML tab to Visual tab with a syntax error,
**I want** the error banner to include the line number from js-yaml,
**so that** I can find and fix the problem without guessing.

**Acceptance criteria:**
- When `jsYaml.load()` throws a `YAMLException`, `useFlowFile` stores `parseError.mark.line + 1` as part of the error message
- The FlowEditor error banner displays e.g. "YAML parse error on line 14: unexpected token"
- If js-yaml does not provide a line number, the banner shows the raw message

## S4: Navigating away from a dirty flow warns the user

**As a** user who has unsaved changes in the FlowEditor,
**I want** a confirmation dialog before I click away to a different file,
**so that** I don't accidentally lose my edits.

**Acceptance criteria:**
- Clicking a different sidebar item while the current flow has `dirty === true` shows a confirm dialog: "You have unsaved changes. Discard and continue?"
- Clicking "Cancel" keeps the current file open
- Clicking "Discard" navigates to the new file without saving
- If the file has no unsaved changes, navigation is instant with no dialog

## S5: useFlowFile and validateFlow have unit test coverage

**As a** developer modifying the FlowEditor,
**I want** unit tests for the two most critical modules,
**so that** regressions in load/save and validation are caught before they ship.

**Acceptance criteria:**
- `studio/vitest.config.ts` exists and `npm run test` (or `npx vitest run`) passes
- `useFlowFile.test.ts` tests: successful load sets `flowData`, read error sets `loadError`, malformed YAML sets `parseError` with line number, save calls `writeFile` IPC
- `validateFlow.test.ts` tests: missing transition target is flagged, unknown agent_map behavior is warned, valid flow returns empty issues array
- All tests pass on first run with no pre-existing failures (pre-flight baseline recorded)

## S6: setup_command.py is split into focused modules

**As a** developer maintaining the installer,
**I want** `setup_command.py` split into CLI, orchestration, and codegen layers,
**so that** each concern is independently testable and a new host adapter requires editing only one file.

**Acceptance criteria:**
- `src/install_cli/cli.py` exists: contains only argparse setup and interactive menu
- `src/install_cli/orchestrate.py` exists: contains `_run_host` and `_run_host_uninstall`
- `src/install_cli/setup_command.py` is a thin dispatcher (under 80 lines) that imports from `cli.py` and `orchestrate.py`
- `python -m pathly_adapters.install_cli --help` still works
- Existing tests in `tests/` still pass
