# Stories — studio-design-polish

_Source: PO_NOTES.md — decomposed, not re-authored._

---

## S-01 — Readable Typography Baseline

**As a** pipeline author working long Studio sessions
**I want** a larger, modern base font (Inter at 15–16px)
**So that** I can read flow labels, form fields, and panel text without eye strain.

**Delivered by:** Conversation 1 (Phase 1)

### Acceptance Criteria

- AC-01-1: Inter font is loaded and applied as the primary font family across all Studio screens. Verified by inspecting `document.body` computed font-family in DevTools — it resolves to "Inter" before any system fallback.
- AC-01-2: Base font size is 14px or larger (configurable via token). Verified by inspecting a body-text element — computed `font-size` is ≥ 14px. (Architect resolved to 14px per ARCH-03 decision)
- AC-01-3: Font loads offline (no network request to CDN at runtime). Verified by opening Studio in Electron with network disabled — Inter renders without fallback.
- AC-01-4: A `--font-family-base` token and a `--font-size-base` token exist in `theme.ts` and are applied through `index.html` or a root CSS rule.
- AC-01-5: No visible overflow or truncation regression in the Sidebar navigation items, property panel labels, or FlowWizard fields. Verified visually by stepping through all main screens.

### Edge Cases

- If component containers use fixed pixel heights, larger font may clip. Spot-fix heights to `min-height` where this occurs. Do not restructure layout.
- Sidebar item text at 15–16px should still fit within the existing sidebar width — verify with longest menu label.

---

## S-02 — Consistent Keyboard Focus Ring

**As a** keyboard-driven user
**I want** every interactive control (Button, Input, IconButton) to share the same visible focus ring
**So that** I always know where my focus is and never get lost tabbing through forms.

**Delivered by:** Conversation 1 (Phase 2)

### Acceptance Criteria

- AC-02-1: A single `--focus-ring` CSS token is defined in `theme.ts` (value: a visible outline, e.g. `2px solid <color> offset 2px`).
- AC-02-2: `Button`, `Input`, and `IconButton` all use `:focus-visible` with `--focus-ring`. Verified by tabbing through a screen containing all three — each shows the same ring style.
- AC-02-3: The ring is visible in both light and dark themes. Verified by toggling theme and tabbing to each control — ring contrasts against both backgrounds.
- AC-02-4: No existing `:focus` or `:focus-visible` overrides in component CSS modules remain that would conflict.

### Edge Cases

- `:focus-visible` is safe in Electron's Chromium. Do not add `:focus` fallback unless a regression is observed.
- If focus ring color matches the dark background exactly, darken the offset or add a white inner glow. Note any such adjustment in code comment.

OPEN: Should `--focus-ring` use the existing `--accent` color value or a new dedicated focus color token? If a new token, PO must confirm the color. Pending PO or architect decision — default to `--accent` until resolved without blocking delivery.

---

## S-03 — Semantic Border Token

**As a** developer maintaining Studio's UI
**I want** a `--border` semantic token in the theme
**So that** borders are consistent across components instead of hardcoded one-off values.

**Delivered by:** Conversation 2 (Phase 3)

### Acceptance Criteria

- AC-03-1: `theme.ts` defines at minimum `--border` (and optionally `--border-subtle`, `--border-strong`) for both light and dark themes.
- AC-03-2: All hardcoded border-color values in `Button.tsx`, `Input.tsx`, `IconButton.tsx`, `Sidebar.module.css`, and `panelStyles.ts` are replaced with `var(--border)` or a variant. Verified by grepping those files for hardcoded hex/rgb border values — zero matches.
- AC-03-3: Visual appearance of borders is unchanged after token replacement (no regressions). Verified by screenshot comparison of each component in both themes.

### Edge Cases

- Some "border" uses may be `box-shadow` dividers — document these separately and do not forcibly replace them with the border token if behavior differs.
- If `--border-subtle` and `--border-strong` are not needed by any component during this story, add only `--border` and note the gap.

---

## S-04 — Motion on Interactive Elements

**As a** Studio user
**I want** subtle 150ms ease-out transitions on hover, active, and snap state changes
**So that** the UI feels responsive and alive rather than jumpy.

**Delivered by:** Conversation 2 (Phase 4)

### Acceptance Criteria

- AC-04-1: A `--transition-base` token is defined in `theme.ts` with value `150ms ease-out`.
- AC-04-2: `Button`, `IconButton`, Sidebar items, and panel buttons use `var(--transition-base)` for their hover/active transitions. Verified by inspecting computed styles — transition value matches the token.
- AC-04-3: A `@media (prefers-reduced-motion: reduce)` rule sets `--transition-base: 0ms` (or equivalent). Verified by enabling reduced-motion in OS settings — no transitions animate.
- AC-04-4: Existing inconsistent inline transition values (`0.12s`, `0.15s`) in FlowWizard and other components are replaced with the token.

### Edge Cases

- Motion on snap state changes (flow canvas) may fire at high frequency. Limit transition to color/background-color/opacity only — do not animate layout properties on high-frequency events.
- If snap state changes already have their own animation system, do not override it. Note the boundary in code comment.

---

## S-05 — Stronger Sidebar Active State

**As a** user navigating between Studio sections
**I want** the active sidebar item to be clearly highlighted
**So that** I always know which section I'm in at a glance.

**Delivered by:** Conversation 2 (Phase 4)

### Acceptance Criteria

- AC-05-1: The active sidebar item is distinguishable from inactive items by at least two visual cues (e.g., background fill + accent left border + bold/accent text). Verified visually in both themes.
- AC-05-2: Active item background color passes WCAG AA contrast (4.5:1) against the active text color in both light and dark themes. Verified via contrast check tool.
- AC-05-3: The existing `.itemRowSelected` CSS class in `Sidebar.module.css` is updated (not duplicated) to implement the new treatment.
- AC-05-4: Inactive items are visually distinct from the active item — no ambiguity when switching between sections. Verified by navigating to each section.

### Edge Cases

- If the strengthened active background is very close to the accent color used for other UI elements, adjust slightly to avoid visual confusion. Document the token choice.
- Panel `.bottomRowActive` button class should receive the same treatment for consistency.

---

## S-06 — FlowWizard Inline Validation and Step Progress

**As a** user filling out the multi-step FlowWizard
**I want** inline validation on each field and a visible step progress indicator
**So that** I know what's wrong before clicking Next and how far I am through the flow.

**Delivered by:** Conversation 3 (Phase 5)

### Acceptance Criteria

- AC-06-1: Each step that has required fields (Steps 1–5) shows an inline error message below the field when the field is invalid and the user has attempted to advance. Verified by submitting an empty required field on each step — error text appears below the field.
- AC-06-2: The "Next" button is disabled (or visually inert with an error state) when the current step's required fields are invalid. Verified by leaving a required field blank — Next does not advance.
- AC-06-3: Error messages clear when the field becomes valid (live validation after first blur or submit attempt). Verified by correcting a flagged field — error disappears.
- AC-06-4: A step progress indicator is visible at the top of the wizard showing both a visual element (dots/bar matching existing `stepDotStyle`) and a text counter ("Step N of 5"). Verified by advancing through all steps — counter and dots update correctly.
- AC-06-5: Validation rules are defined for each step:
  - Step 1 (Name): Flow name non-empty, no duplicate names.
  - Step 2 (States): At least one state defined.
  - Step 3 (Transitions): At least one transition defined, or explicit "skip" allowed.
  - Step 4 (Agents): At least one agent assigned, or explicit "skip" allowed.
  - Step 5 (Review): No required fields — read-only summary, Next/Finish always enabled.
- AC-06-6: `goToStep()` does not clear error state when the user navigates back (errors persist until corrected). Verified by triggering errors, going back, and returning forward — errors remain until fields are fixed.

### Edge Cases

- Steps 3 and 4 allow "skip" — the Next button must be enabled with zero items (they are optional steps). Error validation only applies if the user has partially filled a form entry (e.g., typed a transition source but not a target).
- Duplicate flow name check requires access to existing flows — if that data is not available synchronously, show a deferred async error and do not block immediate Next.
- The existing `handleNext()` validation on Steps 1–2 must be refactored to use the new inline error mechanism rather than running in parallel.

OPEN: Are there specific validation rules beyond "non-empty" for Step 1 (e.g., max length, character restrictions, uniqueness check against persisted data)? If duplicate name check requires an async call, confirm whether it blocks `Next` or shows a deferred warning. Pending PO clarification — default to synchronous non-empty check only until resolved.

---

## S-07 — Light Theme Contrast Compliance

**As a** user on the light theme (including users with low vision)
**I want** secondary text to meet WCAG AA contrast (4.5:1)
**So that** I can read all content comfortably and the product is accessible.

**Delivered by:** Conversation 3 (Phase 6)

### Acceptance Criteria

- AC-07-1: All body and secondary text tokens in the light theme produce a contrast ratio ≥ 4.5:1 against their background. Verified via an automated contrast check tool run against the light theme CSS variables.
- AC-07-2: Dark theme contrast ratios are unaffected (no regression). Verified by running the same check against dark theme tokens — all previously passing values still pass.
- AC-07-3: Any adjusted token values are in `theme.ts` only — no hardcoded color values are introduced to fix contrast.
- AC-07-4: A contrast audit report (stdout or file) is produced as part of this story's completion evidence, listing each token pair checked and its ratio.

### Edge Cases

- If a token is shared between light and dark themes, adjusting it for light-theme contrast may break dark-theme compliance. In this case, split the token into theme-specific variants.
- Decorative text (e.g., placeholder text) intentionally has lower contrast per WCAG — do not force AA on placeholder text; apply AA only to content text.

**Status: DONE** — Resolved via inline Node.js script against theme.ts hex values (no external deps).

### Audit Results (2026-05-19)

**Light theme:**
- textPrimary on bgBase: 14.89:1 PASS
- textPrimary on bgMantle: 13.99:1 PASS
- textPrimary on bgSurface0: 12.04:1 PASS
- textPrimary on bgSurface1: 9.83:1 PASS
- textSecondary on bgBase: 7.60:1 PASS
- textSecondary on bgMantle: 7.14:1 PASS
- textSecondary on bgSurface0: 6.14:1 PASS
- textSecondary on bgSurface1: 5.01:1 PASS
- textMuted: SKIP (decorative/placeholder — WCAG exempt)

**Dark theme (regression check):**
- textPrimary on bgBase: 14.54:1 PASS
- textPrimary on bgMantle: 15.03:1 PASS
- textPrimary on bgSurface0: 11.85:1 PASS
- textPrimary on bgSurface1: 9.43:1 PASS
- textSecondary on bgBase: 7.12:1 PASS
- textSecondary on bgMantle: 7.36:1 PASS
- textSecondary on bgSurface0: 5.80:1 PASS
- textSecondary on bgSurface1: 4.62:1 PASS

All content text pairs pass WCAG AA (4.5:1). No token changes required (AC-07-3 satisfied by default).
