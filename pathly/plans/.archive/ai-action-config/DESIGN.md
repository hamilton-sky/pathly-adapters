# DESIGN — ai-action-config

This is a **consolidation**, not a new visual language. The shared `PromptActionConfig` adopts the existing board-Evaluate popover styling verbatim (it is the most refined of the four surfaces). No new colors, fonts, or spacing scales are introduced — everything resolves from `tokens.css`.

## Design principle

One configurator, one mental model, four contexts. A user who has configured a board Evaluate run should recognize the Split, Analyze, and Comment configurators instantly: same vertical rhythm, same section labels, same engine pill, same footer.

## Component anatomy — `PromptActionConfig`

Ported from `EvalConfigPopover.module.css`. Top-to-bottom:

| Slot | Source pattern | Notes |
|---|---|---|
| Heading | `.heading` | small-caps label, `var(--text-muted)` |
| Preset dropdown | `BoardSelect` + `.sectionLabel` "LENS"/"PRESET"/"ACTION" | leading `Sparkles` icon |
| Prompt banner | `PromptBanner` (eye/pencil toggle) **or** `bannerSlot` | eval default lens passes the read-only skill banner |
| Extra instructions | `.textarea` (rows 3) | hidden when `showExtra={false}` (compact comment card) |
| Engine | `CliSelect` (`Cpu` icon) under "ENGINE" label | the shared engine dropdown across all 4 surfaces |
| Footer note | `.redirect` (optional) | eval-only "Run on this board" hint |
| Footer | `.footer` → Reset · (secondary) · primary | primary label is contextual |

Primary-button label by surface: Evaluate **"Run now"** · Split/Analyze **"Use once"** (+ secondary **"Save default"**) · Comments **"Send to {engine}"**.

## Per-surface placement

- **Evaluate** — unchanged: popover anchored below the Evaluate button, right-aligned, 290px.
- **Split / Analyze** — the existing `PromptPeekModal` card now hosts `PromptActionConfig`; gains the preset dropdown above the prompt textarea. Reset / Use once / Save default / engine keep their positions.
- **Comment card** (`CommentModal`) — compact: swatch row, anchor preview, prompt textarea, then an **action row**: a small `CliSelect` engine pill on the left, primary **"Send to {engine}"** + "Add comment" on the right. `showExtra={false}` keeps the card small. Engine pill uses the same `Cpu`-icon trigger, sized to match the existing buttons.
- **Comments panel header** (`CommentConfigButton`) — a single icon trigger (`Cpu`/`SlidersHorizontal`) at the right of the panel header, opening `PromptActionConfig` as a small popover to set the panel default engine + preset. The footer "Send to Agent" button becomes **"Send to {engine}"**.

## Interaction states

- Engine pill: default / hover / open (chevron rotate) — reuse `CliSelect` states.
- Preset dropdown: reuse `BoardSelect` menu (portaled; outside-click must not close the parent popover — same guard as `EvalConfigPopover`).
- Primary button disabled while a run is in flight (`running`) or input empty (comment send needs non-empty body).
- ⌘/Ctrl+Enter triggers the primary action in every surface.

## Responsive / a11y (CLAUDE.md rules)

- No fixed widths on inner containers; `min-width: 0` on flex children; popover width capped, inner content fluid. Verified ≤200px.
- No inline styles except documented exceptions (positioning custom-props already used by the popovers).
- Every `<button type="button">`; `aria-expanded` on dropdown triggers; engine items `role="menuitemradio"` with `aria-checked` (inherited from `CliSelect`).

## Design System Output

**No new design tokens.** This feature consumes the existing system:

- **Color / spacing / type:** all from `tokens.css` (`var(--bg-mantle)`, `var(--accent)`, `var(--text-primary)`, `var(--text-muted)`, comment accent vars `--comment-*`).
- **Reused components (no restyle):** `CliSelect`, `BoardSelect`, `PromptBanner`, `MarkdownRenderer`.
- **Reused CSS source of truth:** `EvalConfigPopover.module.css` → ported into `PromptActionConfig.module.css` (section label, textarea, footer, redirect, popover shell). Eval's own module keeps only its portal/positioning shell.
- **Icons (Lucide, `currentColor`):** `Sparkles` (preset), `Cpu` (engine), `RotateCcw`/Reset, `ArrowRight` (footer note), `SendHorizonal` (comment send).
- **New CSS modules:** `PromptActionConfig.module.css`, `CommentConfigButton.module.css` — both token-only, no literals.

Net: zero net-new visual primitives; the deliverable is structural reuse. Build may proceed.
