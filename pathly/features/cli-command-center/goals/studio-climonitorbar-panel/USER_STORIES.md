# User Stories — CliMonitorBar UI/UX Design Review (near-term)

> Phase 1 (Conversation 1) delivers all stories.

---

## Story 1 — FLOW label visual hierarchy

**As a** Studio user monitoring a headless run,
**I want** the FLOW section label to be visually heavier than the ACTIVE/RECENT labels,
**so that** I can immediately identify the primary control zone without scanning.

### Acceptance criteria
- `.sectionLabelPrimary` class exists in `CliMonitorBar.module.css` with elevated weight/tracking (≥ 600 weight, letter-spacing 0.08em).
- `CliMonitorBar.tsx:126` FLOW div uses `s.sectionLabelPrimary` (not `s.sectionLabel`).
- ACTIVE and RECENT labels retain `s.sectionLabel` (unchanged).
- No visual regression on QUEUE label inside SpawnQueuePanel (untouched).

---

## Story 2 — FlowControlBar button sizing and disabled state

**As a** Studio user in idle state (no active flow),
**I want** the Start button and toolbar buttons to be slightly larger and clearly disabled-looking when not actionable,
**so that** the primary action is easy to hit and its state is unambiguous.

### Acceptance criteria
- `.btn` height in `FlowControlBar.module.css` = 30px (was 28px) for primary buttons.
- Icon-button variant = 26px (was 24px).
- `.btn:disabled` rule added: `opacity: 0.38; cursor: not-allowed`.
- Disabled Start button (idle state) dims visually — verify in running app.
- Hover state (`:hover:not(:disabled)`) is unaffected.
- Existing `.btnDisabled` class and `:hover:not(:disabled)` guard compose cleanly with the new rule.

---

## Story 3 — Body padding token alignment

**As a** developer maintaining the Studio design system,
**I want** the CliMonitorBar `.body` padding to use spacing tokens instead of a hardcoded value,
**so that** the panel respects the shared spacing scale.

### Acceptance criteria
- `CliMonitorBar.module.css:105` `.body` padding = `var(--space-2) var(--space-1)` (8px/4px).
- No hardcoded `4px` remains on `.body`.
- Visual change is minimal (4px → 8px vertical); session rows remain unclipped.

---

## Verification (non-story)

- Steps 1, 2, 4, 5, 6 of DESIGN_REVIEW.md confirmed still-shipped in source (read-only check, no edit).
- Step 8 intentionally skipped — separator already present via FlowControlBar wrapper border.
- Step 3c intentionally skipped — CodeIntelControl owns its own toggle styling.
- `tsc --noEmit` passes clean after all changes.
