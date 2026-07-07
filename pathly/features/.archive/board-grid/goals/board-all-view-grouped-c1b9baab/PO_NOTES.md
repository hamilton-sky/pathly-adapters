# PO Notes — board-grid

_Last updated: 2026-07-06_

## Who Is This For

A **human supervisor** monitoring headless multi-agent runs in the Studio Command Center
(`CommsPanel`). Their primary pain: the board has three filtered tabs (Messages / Goals & Tasks /
Artifacts) but no single view that shows everything at once. They need to scan the whole board —
goals, tasks, messages, and artifacts — like a dense ticket board, without scrolling through
multiple tabs or loading full message cards.

## Definition of Success

A 4th **"All"** tab appears in `BoardViewToggle`. Selecting it shows the full board content as
compact tiles, **banded by kind** (Goals → Tasks → Messages → Artifacts), each band with a count
header. Each tile shows type badge + title + meta; clicking opens the correct existing detail modal.
The view degrades gracefully: multi-column at ≥600px, single column at <400px, and a placeholder
banner at ≤~220px (never a degenerate duplicate of the Messages tab). The three existing tabs are
unchanged. Passes `tsc --noEmit`.

## Out of Scope

- No Kanban drag-and-drop (separate, larger feature).
- No new authoring surface — composing still happens via the footer input.
- No changes to the data model or what gets posted to the board.
- P3 drag-to-status mode is explicitly deferred and only built if explicitly requested.
- No new status columns, swimlanes, or filtering controls inside GridView.

## Constraints

- **Reuse first:** `MessageTypeBadge` (13 type colours), `GoalDetailModal`, `ArtifactModal`,
  `container-type: inline-size` breakpoint pattern from `BoardViewToggle.module.css`.
- **No inline styles** — CSS modules + `tokens.css` variables only; `data-*` attribute variant
  pattern for per-type tile tints.
- **Component size cap:** ~150 lines per file; every component in its own folder.
- Must pass `tsc --noEmit -p studio/tsconfig.web.json`.
- Must be verified at ≤200px (placeholder banner) and ~700px (multi-column grid).
- Studio responsiveness rule: all components resize with panel; `min-width:0` on flex children.

## Working Assumptions (Open Questions Resolved)

1. **Tasks band layout** — flat, not nested under goals. Each task tile links to its goal's
   `GoalDetailModal` (focused on that task). Ungrouped tasks do not form sub-headers.
2. **Narrow (<~220px) strategy** — **placeholder banner** ("Grid view is best in a wider board —
   expand this panel") with an expand affordance. Do NOT degrade to a 1-column list that just
   duplicates the Messages tab.
3. **Message detail modal** — use `MsgCard` in a generic modal shell for P1. Avoid creating a
   dedicated `MessageDetailModal` until there is a clear need beyond P1.
4. **Pinned / phase rows** — **include** in the "All" grid (it is the overview; completeness is
   the point). Star marker is optional polish for P2.

## Open Questions

- Tasks clicking into `GoalDetailModal`: confirm whether the modal supports a `focusTaskId` prop
  or needs a small extension to scroll-to/highlight the specific task. (Working assumption:
  open the goal modal at the top; task highlight is P2 polish.)
