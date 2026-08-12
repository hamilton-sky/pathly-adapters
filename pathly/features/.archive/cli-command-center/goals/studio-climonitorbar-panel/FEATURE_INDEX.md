# Feature Index — CliMonitorBar UI/UX Design Review (near-term)

> Goal: studio-climonitorbar-panel-a-ui-ux-design-review-3453c9bb
> Feature: cli-command-center
> Rigor: lite

## What this goal delivers

A targeted CSS/TSX styling pass on the Studio CliMonitorBar ("Command Center") panel.
The original DESIGN_REVIEW.md prescribed 9 steps; steps 1, 2, 4, 5, 6 are already
shipped in the current source. This goal implements the 3 remaining changes and
verifies the already-shipped ones.

## Files changed

| File | Change |
|------|--------|
| `studio/src/renderer/src/components/CliMonitorBar/CliMonitorBar.module.css` | Add `.sectionLabelPrimary`; fix `.body` padding |
| `studio/src/renderer/src/components/CliMonitorBar/CliMonitorBar.tsx` | Swap FLOW label class to `.sectionLabelPrimary` |
| `studio/src/renderer/src/components/HQ/FlowControlBar/FlowControlBar.module.css` | `.btn` height bump + `.btn:disabled` rule |

## Non-goals

- `.sectionLabelMeta` / step 3c — superseded by CodeIntelControl's own styling
- `.flowSection border-bottom` / step 8 — separator already exists via FlowControlBar wrapper
- North-star CliCommandCenter modal — separate future goal
- No Python / FSM / IPC changes

## Key references

- `ARCHITECTURE_PROPOSAL.md` — staleness audit + remaining build contract
- `DESIGN.md` — design system tokens + anti-patterns
- `pathly/plans/cli-command-center/DESIGN_REVIEW.md` — original review
