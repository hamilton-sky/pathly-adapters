# Feature Index — studio-sidebar-redesign

## Summary

Redesign the Pathly Studio sidebar from a manually-toggled tab panel into a context-aware, visually polished interface that automatically shows the right content based on which main panel is active, presents the global library as a browsable card grid with pill filters, and enables drag-to-canvas for all library item types.

## Rigor

standard

## Stories

| ID | Title | Conversation |
|----|-------|--------------|
| S1 | Context-aware sidebar driven by activePanel | Conv 1 |
| S2 | Move plan folder list into Monitor panel body | Conv 1 |
| S3 | Library card grid with pill filter tabs | Conv 2 |
| S4 | My Library compact chip row | Conv 2 |
| S5 | Drag library items onto Canvas | Conv 3 |
| S6 | Sidebar visual system tokens | Conv 2 |

## Conversations

| Conv | Title | Stories | Status |
|------|-------|---------|--------|
| 1 | Context-aware sidebar switch | S1, S2 | TODO |
| 2 | Library card grid + pill filters + My Library chips | S3, S4, S6 | TODO |
| 3 | Drag-to-canvas for all library item types | S5 | TODO |

## Files In Play

- `studio/src/renderer/src/components/sidebar/Sidebar.tsx`
- `studio/src/renderer/src/components/sidebar/shell/TabBar.tsx` — replaced by `SidebarHeader.tsx`
- `studio/src/renderer/src/components/sidebar/shell/SidebarHeader.tsx` — new file
- `studio/src/renderer/src/components/sidebar/panels/WorkspacePanel.tsx`
- `studio/src/renderer/src/components/sidebar/panels/LibraryPanel.tsx`
- `studio/src/renderer/src/components/sidebar/Sidebar.module.css`
- `studio/src/renderer/src/components/Monitor/index.tsx`
- `studio/src/renderer/src/components/Monitor/PlanProgress.tsx` — new file
- `studio/src/renderer/src/types/index.ts` — drag MIME/shape reference only

## Key Constraints

- `activePanel` Zustand store drives sidebar context (no local tab state)
- Sidebar background `#0d0d14`, width `280px`
- Existing canvas drop handler contract (`PathlyCanvasDragItem`, `dragType: 'canvas'`) must not be broken
- `npm run typecheck` must pass after every conversation
- No commit to master without explicit user approval

## Open Items From PO Notes

The following open questions from PO_NOTES.md are noted for architect/builder awareness. They do not block planning but must be resolved before or during the relevant conversation.

- OPEN: Exact name and path of the Monitor panel component hosting plan progress rows. Scout finding: `studio/src/renderer/src/components/Monitor/index.tsx`.
- OPEN: Source of "Debugs / Explorations / Lessons / Pipeline-walkthrough" data in WorkspacePanel — static folders or FSM-driven?
- OPEN: Source of truth for "My Library" items — local-only, synced, or per-project?
- OPEN: Section header (replacing TabBar) — purely text or include context icon?
- OPEN: Pill filter tabs — single-select or multi-select?
- OPEN: Default selected pill filter on first Canvas open.
- OPEN: Drag preview/ghost styling — browser default or custom drag image?
- OPEN: Hover/active states for cards and chips — from design system or to be specified?
