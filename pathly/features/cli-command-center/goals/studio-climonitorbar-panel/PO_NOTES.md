# PO Notes — CliMonitorBar UI/UX Design Review (near-term)

> Auto-generated from board decisions + ARCHITECTURE_PROPOSAL.md + DESIGN_REVIEW.md (autoFlow mode)

## Problem statement

The CliMonitorBar panel ("Command Center") is visually under-differentiated — the FLOW primary zone lacks typographic weight and the FlowControlBar buttons are slightly undersized. Steps 1, 2, 4, 5, 6 of the original DESIGN_REVIEW.md are already shipped. Three CSS changes and one TSX className swap remain.

## Scope (near-term)

Three atomic CSS/TSX changes derived from the design review and ratified by the architect:

1. **Visual hierarchy** — add `.sectionLabelPrimary` CSS class and apply it to the `FLOW` section label (`CliMonitorBar.tsx:126`). This lifts the primary zone's typography above secondary labels.
2. **Button sizing** — bump `FlowControlBar` `.btn` height 28→30px / icon-btn 24→26px and add `.btn:disabled` rule (`opacity: 0.38; cursor: not-allowed`). RunnerBtn already sets `disabled={!enabled}` semantically; this makes the visual state explicit.
3. **Body padding token** — change `.body` hardcoded `4px` to `var(--space-2) var(--space-1)` (8px/4px) for token alignment.

## Explicitly out of scope

- Step 3c (`.sectionLabelMeta`) — superseded; CodeIntelControl owns its own `.sectionToggle` styling.
- Step 8 (`.flowSection border-bottom`) — skip; separator already exists via `FlowControlBar .wrapper`.
- Steps 1, 2, 4, 5, 6 — already shipped; verify only.
- North-star `CliCommandCenter` modal — separate future goal.
- No FSM / HTTP / Python changes. Pure renderer CSS Modules + one TSX class.

## Acceptance

- FLOW label renders with noticeably heavier weight/tracking than ACTIVE/RECENT labels.
- FlowControlBar buttons are 30px tall (primary) / 26px (icon), and disabled Start button dims (`opacity ~0.38`, `cursor: not-allowed`).
- `.body` section uses `var(--space-2) var(--space-1)` padding — no hardcoded `4px`.
- No regressions on collapsed CodeIntelControl or session rows.
- `tsc --noEmit` passes clean.
