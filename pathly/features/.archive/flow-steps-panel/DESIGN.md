# Design — Flow Steps Dock

**Author:** designer · **Feature:** flow-steps-panel · **Date:** 2026-07-16

## Surface
A thin (~214px) right-docked panel in the Monitor, collapsible to a ~34px rail — the same
open/collapse affordance as the Skill Composition sidebar. It replaces the removed top pipeline bar.

## Dock states
- **Expanded, flow running** — header + (optional) flow tabs + stepper + control footer.
- **Collapsed** — rail: a chevron, a vertical `FLOW` label, and a status dot (green = a flow is live).
- **Idle (no flow)** — collapsed by default; expanding shows an empty state
  ("No flow running — start one from the board").

## Header
Collapse chevron · flow name (mono, ellipsized) · a current-state badge (accent pill). If >1 flow
runs, a compact row of flow tabs under the header to switch which run the dock shows.

## Stepper (vertical)
Each phase = a dot on a connector rail + label + role · engine:
- **done** — teal `#1D9E75` fill + check; the connector above it teal `#5DCAA5`.
- **current** — accent `#378ADD` fill + play glyph, a 3px `--bg-accent` halo; label in
  `--text-accent`, suffix "· running".
- **upcoming** — gray hollow ring `#B4B2A9`; label `--text-secondary`.
Gate / terminal-precursor states (`NO_DAG_SEEDED`, …) are omitted from the steps.

## Reroute footer
A `--surface-1` footer: a pause/resume icon button, a `next →` `<select>` of the flow's
reachable-next states (+ "Back to <stage>"), and a full-width **Reroute** button. Caption:
"keeps the current model · <model>". Reroute is a deliberate, low-frequency action → secondary
button styling, never a primary CTA.

## Tokens / a11y
All color via `tokens.css` vars (plus the fixed status hexes for the dots, which are mode-stable
small indicators). `type="button"` everywhere; `aria-expanded` on the collapse control; `aria-label`
on icon-only buttons; the stepper is a semantic ordered list. Responsive: `min-width:0`, no fixed
widths beyond the dock/rail; verified ≤200px wide.

## Interaction
Click a flow card in the Monitor → the dock expands to that run. Toggle collapse ⇄ rail. Pick a
next state → **Reroute** → the run continues there. Switch flow tabs → the dock re-renders that
run's stepper. Everything is derived from the running flow's own `states`, so a **user-created
flow** shows correctly the moment it's activated — no per-flow code.
