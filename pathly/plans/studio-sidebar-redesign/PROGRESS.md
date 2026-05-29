# Progress — studio-sidebar-redesign

| Conv | Title | Stories | Status |
|------|-------|---------|--------|
| 1 | Context-aware sidebar switch | S1, S2 | DONE |
| 2 | Library card grid + pill filters + My Library chips | S3, S4, S6 | TODO |
| 3 | Drag-to-canvas for all library item types | S5 | TODO |

## Story Status

| Story | Title | Conv | Status |
|-------|-------|------|--------|
| S1 | Context-aware sidebar driven by activePanel | 1 | TODO |
| S2 | Move plan folder list into Monitor panel body | 1 | TODO |
| S3 | Library card grid with pill filter tabs | 2 | TODO |
| S4 | My Library compact chip row | 2 | TODO |
| S5 | Drag library items onto Canvas | 3 | TODO |
| S6 | Sidebar visual system tokens | 2 | TODO |

## Acceptance Criteria Checklist

### Conv 1 — S1

- [ ] AC1.1: `activePanel === 'monitor'` → sidebar shows Workspace only
- [ ] AC1.2: `activePanel === 'flow'` → sidebar shows Library only
- [ ] AC1.3: No tab bar or toggle visible; `TabBar.tsx` replaced by `SidebarHeader.tsx`
- [ ] AC1.4: `SidebarHeader.tsx` renders plain text label ("Workspace" or "Library")
- [ ] AC1.5: 150ms opacity + y-translate transition on context switch; no stacking on rapid switch
- [ ] AC1.6: Unknown `activePanel` values fall back to Workspace
- [ ] AC1.7: Zero references to `switchTab` or `libraryOpen` in sidebar components
- [ ] AC1.8: `tsc --noEmit` passes

### Conv 1 — S2

- [ ] AC2.1: `PlanSection` removed from `WorkspacePanel.tsx`
- [ ] AC2.2: Monitor renders plan rows above event log
- [ ] AC2.3: Plan rows use `usePlanFiles()` hook or equivalent data source
- [ ] AC2.4: Sidebar workspace shows only Debugs, Explorations, Lessons, Pipeline-walkthrough
- [ ] AC2.5: Plan rows have `max-height` + `overflow-y: auto` for short viewports
- [ ] AC2.6: `tsc --noEmit` passes

### Conv 2 — S3

- [ ] AC3.1: File-system tree removed from `LibraryPanel.tsx`; 2-col card grid in its place
- [ ] AC3.2: Pill tabs: ALL | FLOWS | SKILLS | AGENTS | TEMPLATES displayed
- [ ] AC3.3: Pill tabs are single-select; ALL shows all types
- [ ] AC3.4: Type-color left-border accents on cards (Flows=#00ff87, Skills=#ff9f43, Agents=#6c72ff, Templates=#ff6b9d)
- [ ] AC3.5: Labels in JetBrains Mono; descriptions in base sans-serif
- [ ] AC3.6: Long titles truncate with CSS ellipsis
- [ ] AC3.7: Empty-state message when no items match selected filter
- [ ] AC3.8: Global library header uses `--accent-global: #00ff87`
- [ ] AC3.9: `tsc --noEmit` passes

### Conv 2 — S4

- [ ] AC4.1: "My Library" section renders below global library section
- [ ] AC4.2: Items render as horizontal scroll chip row (not grid)
- [ ] AC4.3: Chips use `--accent-mine: #6c72ff` accent
- [ ] AC4.4: Zero chips → empty-state placeholder renders
- [ ] AC4.5: Chip row scrolls horizontally; sidebar width does not expand
- [ ] AC4.6: `tsc --noEmit` passes

### Conv 2 — S6

- [ ] AC6.1: Sidebar `background: #0d0d14`, `width: 280px` applied
- [ ] AC6.2: CSS custom properties defined: `--accent-global`, `--accent-mine`, `--type-flow`, `--type-skill`, `--type-agent`, `--type-template`
- [ ] AC6.3: JetBrains Mono on card labels; sans on descriptions
- [ ] AC6.4: New tokens scoped to sidebar module; no global leakage
- [ ] AC6.5: `tsc --noEmit` passes

### Conv 3 — S5

- [ ] AC5.1: All library cards have `draggable={true}` with `application/pathly-drag-item` MIME key
- [ ] AC5.2: Nested Flow items are individually draggable; parent drag does not fire (stopPropagation)
- [ ] AC5.3: My Library chips have `draggable={true}` with same MIME key
- [ ] AC5.4: Drag payload satisfies `PathlyCanvasDragItem` contract (`dragType: 'canvas'`, name, section, path)
- [ ] AC5.5: `cursor: grab` on hover; `cursor: grabbing` while dragging
- [ ] AC5.6: Drag-handle affordance visible by default (not hover-only)
- [ ] AC5.7: Canvas drop handler unchanged and functional
- [ ] AC5.8: `tsc --noEmit` passes
