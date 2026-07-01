# Board "All" view — grouped ticket-grid overview

**Feature id:** `board-grid`
**Surface:** Studio Command Center → `CommsPanel`
**Status:** spec (design agreed; not built)

## Summary

Add a 4th board view to the Command Center — an at-a-glance **overview** that renders
everything on the board as compact tiles, **banded by kind** (Goals · Tasks · Messages ·
Artifacts) rather than one flat uniform pile. Clicking a tile opens the existing detail
modal for that item. This is a **read / triage** surface — not a new authoring place, and
not a Kanban with drag.

## Motivation

The board has three filtered tabs (Messages / Goals & Tasks / Artifacts). None gives a
single-glance overview of *everything* on the board. The user (a human supervising
headless agent runs) wants to scan the whole board like a ticket board — dense,
colour-coded, click for detail. The Messages tab today is a vertical scroll of heavy full
cards; it does not scan.

## Decisions carried in from the PO + designer consult

- **PO:** an "everything" grid must not merely duplicate the three filtered tabs, and must
  **not flatten the goal → task → message → artifact hierarchy** into uniform peer tiles —
  that hierarchy is what makes the board legible. It earns its place only as an *overview*.
- **Designer:** a grid needs width; at ≤200px it collapses to one column (= a worse
  Messages list). So it must degrade gracefully and is primarily for the expanded/wide
  board. Reuse `MessageTypeBadge` colours and the existing modal pattern.
- **User decision (the reconciliation):** dense, ticket-like **tiles** (the "flat grid"
  feel) **but grouped/banded by kind** so the hierarchy survives (the "grouped overview"
  structure). This is options 1+2 merged.

## Scope — what to build

1. Add a 4th entry to `BoardViewToggle`:
   `BoardView = 'messages' | 'goals' | 'artifacts' | 'grid'`. Label **"All"**, icon
   `LayoutGrid`. Labels already collapse to icon-only at ≤400px via the existing
   container query — verify 4 icons fit at 200px.
2. New `GridView`, rendered by `CommsPanel` when `boardView === 'grid'`.
3. GridView content is **banded by kind**, in order, each band a small header
   (e.g. `Goals · 3`) over a responsive tile grid:
   - **Goals** (with a task rollup count)
   - **Tasks**
   - **Messages** (thread types: nudge, decision, question, answer, discovery, note,
     status, phase, warning, escalation, and artifact-as-message)
   - **Artifacts**
4. **Tile anatomy** — compact, fixed height ~72–84px, ~2 lines:
   - Row 1: `MessageTypeBadge` (reuse) + optional status dot (goal/task: running /
     blocked / done).
   - Row 2: title / first line of text, clamped to 2 lines (`-webkit-line-clamp: 2`).
   - Row 3 (meta, 11px mono): author + relative time; artifacts show atype (md/pdf/…);
     tasks show executor / status.
   - Tile background tinted by `data-type` using the existing MessageTypeBadge token
     families. **No action buttons on the tile** — actions live in the modal.
5. **Click a tile → open the item's detail modal** (reuse where possible):
   - goal → `GoalDetailModal` (initialGoalId = goal id)
   - artifact → `ArtifactModal`
   - task → `GoalDetailModal` focused on the task's goal (open question below)
   - message → `MessageDetailModal` (NEW lightweight modal, or `MsgCard` in a modal shell)
6. **Responsive** (container query on GridView, mirroring `BoardViewToggle.module.css`
   `container-type: inline-size`):
   - ≥600px → 3-column grid (min tile ~180px)
   - 400–599px → 2-column
   - <400px → 1-column list
   - ≤~220px (docked narrow) → a **placeholder banner** ("Grid view is best in a wider
     board — expand this panel") with an expand affordance, instead of a degenerate
     1-column list that just duplicates Messages.

## Reuse (do not reinvent)

- `MessageTypeBadge` — all 13 type colours already exist (`data-type`).
- `GoalDetailModal`, `ArtifactModal` — the card→modal pattern is established.
- `container-type: inline-size` breakpoint idiom from `BoardViewToggle.module.css`.
- Kind-splitting logic already present in `CommsMsgList` (excludes goal/task) and
  `GoalsView` (goals + tasks-by-goal) — factor the split into a shared pure helper.

## Non-goals

- **Not** a Kanban with draggable status columns — separate, larger feature. Read-only +
  click-to-detail only.
- **Not** a new authoring surface — composing still happens via the footer input.
- **Not** a change to the message model or what gets posted — presentation layer only.
  The board is also agent memory; do not mutate the data model for the human view.

## Design rules to honor (studio/CLAUDE.md)

- No inline styles; CSS modules + `tokens.css` variables only.
- `data-*` attribute variant pattern for the per-type tile tint.
- Every component in its own folder; ~150-line cap; extract sub-components.
- Verified at ≤200px (hence the placeholder-banner strategy) and at ~700px.
- `type="button"`, ARIA spread pattern, no `overflow: visible` on scroll containers.

## Suggested component layout

```
CommsPanel/
  GridView/
    GridView.tsx          bands + responsive grid; renders a tile grid per kind
    GridView.module.css
    Tile/
      Tile.tsx            one compact tile (badge + title + meta); click → onOpen
      Tile.module.css
    gridBands.ts          pure: split Message[] → { goals, tasks, messages, artifacts }
  MessageDetailModal/     NEW, only if we choose a dedicated message modal
    MessageDetailModal.tsx
    MessageDetailModal.module.css
```

## Phasing

- **P1:** GridView with the four bands + Tile + responsive grid/list + placeholder banner;
  wire click → existing `GoalDetailModal` / `ArtifactModal`; messages open a minimal modal
  (or `MsgCard` in a modal shell).
- **P2:** density polish, status dots, per-type tints, empty state ("Nothing on this board
  yet — start a goal or post a message").
- **P3 (only if asked):** drag-to-status Kanban mode.

## Open questions (for PO / architect)

1. **Tasks band** — show all tasks flat, or nested under their goal (showing only
   ungrouped tasks here)? Simplest P1: one Tasks band; each tile links to its goal's DAG
   modal.
2. **Narrow (<~220px)** — hard-hide the grid behind an "expand" banner, or degrade to a
   1-column list? Leaning: banner (don't duplicate the Messages tab).
3. **Message detail** — dedicated `MessageDetailModal`, or reuse `MsgCard` in a generic
   modal shell?
4. **Pinned / phase rows** — include in "All" (it's the overview) with a star marker, or
   exclude? Leaning: include everything.

## Acceptance criteria

- A 4th **All** tab appears; selecting it shows tiles banded by kind (Goals / Tasks /
  Messages / Artifacts), each band with a count header.
- Each tile shows type badge + title + meta, is keyboard-focusable, and Enter/click opens
  the correct detail modal.
- ≥600px → multi-column grid; <400px → single column; ≤~220px → placeholder banner
  (no degenerate list).
- No inline styles; passes `tsc --noEmit -p studio/tsconfig.web.json`; verified at 200px
  and ~700px.
- The three existing tabs (Messages / Goals & Tasks / Artifacts) are unchanged.
