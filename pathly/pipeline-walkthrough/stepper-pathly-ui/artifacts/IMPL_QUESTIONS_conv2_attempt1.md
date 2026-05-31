[REQ] Three required topbar panel testids have no corresponding buttons in the topbar

## Blocking question

The spec requires:
- `topbar-panel-plan`
- `topbar-panel-editor`
- `topbar-panel-settings`

Investigation result: None of these panel buttons exist in `topbar/index.tsx` or its sub-components (`PanelNav.tsx`, `EditorLauncher.tsx`, `TopicSelector.tsx`, etc.). The only panel-switching buttons in the topbar are `flow` and `monitor` (in `PanelNav.tsx`) — those have been given testids as required.

The `plan` panel is activated by clicking items in the Sidebar tree.
The `editor` panel is activated by clicking files in the Sidebar tree.
The `settings` panel is activated via `BottomNav` inside the Sidebar component (not the topbar).

## Options

1. **Do nothing** — accept that only 17 of 20 testids can be placed (flow + monitor are done; plan/editor/settings have no topbar button). Update the spec to remove these 3.
2. **Add buttons to PanelNav** — extend `PanelNav.tsx` to include plan, editor, settings toggle buttons (new functionality, out of scope for testid-only change).
3. **Add testids to Sidebar/BottomNav** — rename the required testids to reflect they're in the sidebar (e.g. `sidebar-panel-settings`) and add them there instead.

## What I did complete

- `topbar-panel-flow` added to PanelNav.tsx ✓
- `topbar-panel-monitor` added to PanelNav.tsx ✓
- All 15 other required testids are present and TypeScript passes ✓

Awaiting direction on the 3 missing ones before marking this conversation done.
