# Plan — studio-design-polish

_Rigor: lite. Scope: token system + typography + focus + motion + sidebar + wizard validation._

---

## Feature Summary

Polish Pathly Studio's desktop UI by introducing a token-driven design system: Inter font, semantic border/motion/focus tokens, stronger sidebar active state, FlowWizard inline validation + step progress, and light-theme contrast compliance. No component API changes. No visual redesign.

**Primary users:** Pipeline authors, operators (long sessions). Secondary: reviewers, new developers.

---

## Traceability

| Story | Phase | Conversation |
|---|---|---|
| S-01 Typography Baseline | Phase 1 | Conv 1 |
| S-02 Focus Ring | Phase 2 | Conv 1 |
| S-03 Border Token | Phase 3 | Conv 2 |
| S-04 Motion Tokens | Phase 4 | Conv 2 |
| S-05 Sidebar Active State | Phase 4 | Conv 2 |
| S-06 FlowWizard Validation + Progress | Phase 5 | Conv 3 |
| S-07 Light Theme Contrast | Phase 6 | Conv 3 |

---

## Conversation 1 — Token Foundation + Typography + Focus

**Stories delivered:** S-01, S-02
**Goal:** Introduce the token foundation. By end of this conversation, Studio loads Inter at 15–16px and all focusable primitives share a single visible focus ring. The app must remain fully runnable after each phase.

### Phase 1 — Typography Token + Inter Font

**Stories:** S-01

**Scope:**
1. Add `--font-family-base` and `--font-size-base` tokens to `theme.ts` for both light and dark themes (same values — typography tokens are theme-independent).
2. Bundle Inter font in `studio/src/renderer/` as static assets (e.g., `assets/fonts/Inter-*.woff2`). No CDN.
3. Add `@font-face` declarations in `index.html` or a root CSS file pointing to the bundled files.
4. Apply `font-family: var(--font-family-base)` and `font-size: var(--font-size-base)` to `:root` or `body`.
5. Remove or replace any hardcoded `font-size: 12px / 13px / 14px` inline values in `panelStyles.ts` and `FlowWizard.styles.ts` — replace with `var(--font-size-base)` or a relative unit.

**Key files:**
- `studio/src/renderer/src/theme.ts`
- `studio/src/renderer/index.html`
- `studio/src/renderer/src/styles/panelStyles.ts`
- `studio/src/renderer/src/components/FlowWizard/FlowWizard.styles.ts`

**Leave runnable:** App opens, Inter is visible in DevTools, no layout breakage.

**Verify:**
- AC-01-1, AC-01-2, AC-01-3, AC-01-4, AC-01-5

---

### Phase 2 — Focus Ring Token

**Stories:** S-02

**Scope:**
1. Add `--focus-ring` token to `theme.ts` (e.g., `2px solid var(--accent)` with `outline-offset: 2px`). See OPEN in S-02 for color decision — default to `--accent`.
2. Apply `:focus-visible { outline: var(--focus-ring); outline-offset: 2px; }` to `Button.tsx`, `Input.tsx`, `IconButton.tsx`.
3. Remove any conflicting existing `:focus` or `:focus-visible` overrides in those components' CSS modules.
4. Verify ring in both themes.

**Key files:**
- `studio/src/renderer/src/theme.ts`
- `studio/src/renderer/src/components/ui/Button.tsx` (+ its CSS module if present)
- `studio/src/renderer/src/components/ui/Input.tsx` (+ its CSS module)
- `studio/src/renderer/src/components/ui/IconButton.tsx` (+ its CSS module)

**Leave runnable:** All three controls show a focus ring when tabbed to.

**Verify:**
- AC-02-1, AC-02-2, AC-02-3, AC-02-4

---

## Conversation 2 — Border + Motion + Sidebar

**Stories delivered:** S-03, S-04, S-05
**Goal:** Harden the token system with borders and motion, and make the sidebar active state unambiguous. App remains runnable after each phase.

### Phase 3 — Border Token

**Stories:** S-03

**Scope:**
1. Add `--border` to `theme.ts` for both themes (light: subtle mid-gray; dark: surface-adjacent).
2. Add `--border-subtle` and `--border-strong` only if an existing component already has two distinct border intensities — otherwise defer.
3. Replace hardcoded border-color values in: `Button.tsx`, `Input.tsx`, `IconButton.tsx`, `Sidebar.module.css`, `panelStyles.ts`.
4. Do not change `box-shadow` divider patterns — document them with a `/* divider, not border token */` comment.

**Key files:**
- `studio/src/renderer/src/theme.ts`
- `studio/src/renderer/src/components/ui/Button.tsx`
- `studio/src/renderer/src/components/ui/Input.tsx`
- `studio/src/renderer/src/components/ui/IconButton.tsx`
- `studio/src/renderer/src/components/Sidebar.module.css`
- `studio/src/renderer/src/styles/panelStyles.ts`

**Leave runnable:** No visual regressions in border rendering.

**Verify:**
- AC-03-1, AC-03-2, AC-03-3

---

### Phase 4 — Motion Token + Sidebar Active State

**Stories:** S-04, S-05

These two are grouped because the sidebar active state also needs the motion token applied to its transition.

**Scope (Motion — S-04):**
1. Add `--transition-base: 150ms ease-out` to `theme.ts`.
2. Add `@media (prefers-reduced-motion: reduce) { :root { --transition-base: 0ms; } }` in root CSS or `index.html`.
3. Replace `transition: 0.12s`, `transition: 0.15s`, and other ad-hoc transition values in `Button.tsx`, `IconButton.tsx`, `Sidebar.module.css`, `panelStyles.ts`, `FlowWizard.styles.ts` with `var(--transition-base)`.
4. Limit snap-state transitions to `background-color`, `color`, `opacity` only — not layout properties.

**Scope (Sidebar — S-05):**
1. Update `.itemRowSelected` in `Sidebar.module.css`:
   - Increase background fill intensity (use a surface token one level darker than current `--bg-surface0`).
   - Keep the existing `border-left-color: var(--accent)` accent bar. Increase bar width from current value to 3px if currently thinner.
   - Set `font-weight: 600` (or semibold) on active item text.
   - Apply `transition: var(--transition-base)` to the row.
2. Apply the same treatment to `.bottomRowActive` panel button class for consistency.
3. Verify contrast of active text on active background meets AC-05-2 in both themes.

**Key files:**
- `studio/src/renderer/src/theme.ts`
- `studio/src/renderer/src/components/Sidebar.module.css`
- `studio/src/renderer/src/components/ui/Button.tsx`
- `studio/src/renderer/src/components/ui/IconButton.tsx`
- `studio/src/renderer/src/styles/panelStyles.ts`
- `studio/src/renderer/src/components/FlowWizard/FlowWizard.styles.ts`

**Leave runnable:** Sidebar active state visible, transitions working, reduced-motion respected.

**Verify:**
- AC-04-1, AC-04-2, AC-04-3, AC-04-4
- AC-05-1, AC-05-2, AC-05-3, AC-05-4

---

## Conversation 3 — FlowWizard Validation + Contrast Audit

**Stories delivered:** S-06, S-07
**Goal:** Make the FlowWizard production-quality with inline validation and step progress. Audit and fix light-theme contrast.

**Prerequisite:** S-07 requires architect decision on audit tool (see ARCH_QUESTION in S-07). Phase 6 must not begin until that is resolved. Phase 5 is independent and can proceed.

### Phase 5 — FlowWizard Inline Validation + Step Progress

**Stories:** S-06

**Scope:**
1. Add a `stepErrors` state map (`Record<number, Record<string, string>>`) to `FlowWizard.tsx` — keyed by step index, then field name.
2. Add a `touched` state map to track whether user has attempted to advance past a step (errors only display after first advance attempt on that step, not on initial render).
3. Define validation rules per step in a pure `validateStep(step, values)` function (separate file `FlowWizard.validation.ts`):
   - Step 1: `name` non-empty (max-length and uniqueness per OPEN in S-06 — default: non-empty only).
   - Step 2: `states` array length ≥ 1.
   - Step 3: `transitions` array length ≥ 1, OR step is explicitly skipped (skip flag or empty allowed — see AC-06-5).
   - Step 4: `agents` array length ≥ 1, OR step is explicitly skipped.
   - Step 5: always valid (read-only review).
4. Refactor `handleNext()` to call `validateStep()` and populate `stepErrors`. Remove the existing ad-hoc validation logic on Steps 1–2 and route it through the new system.
5. Disable the Next button when `validateStep()` returns errors for the current step.
6. Render inline error messages below each field using a shared `<FieldError>` component (new, in `ui/`).
7. Errors persist through `goToStep()` navigation — do not clear `stepErrors` on step change.
8. Add a text counter `"Step N of 5"` above the existing step dots in the wizard header. The existing `stepDotStyle()` dots remain; add the counter as a sibling text element.

**Key files:**
- `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx`
- `studio/src/renderer/src/components/FlowWizard/FlowWizard.styles.ts` (new: counter style)
- `studio/src/renderer/src/components/FlowWizard/FlowWizard.validation.ts` (new)
- `studio/src/renderer/src/components/ui/FieldError.tsx` (new)

**Leave runnable:** Wizard can be completed end-to-end; errors display correctly; step counter visible.

**Verify:**
- AC-06-1, AC-06-2, AC-06-3, AC-06-4, AC-06-5, AC-06-6

---

### Phase 6 — Light Theme Contrast Compliance

**Stories:** S-07

**Prerequisite:** Architect must confirm audit tool before this phase begins (see ARCH_QUESTION in S-07).

**Scope:**
1. Run the chosen contrast audit tool against all `--text-*` / `--fg-*` token pairs and their corresponding background tokens in the light theme.
2. For any pair failing 4.5:1, adjust the text token value in `theme.ts` (light theme section only) until it passes.
3. Re-run audit against dark theme to confirm no regressions.
4. If any adjusted token is shared between themes (same variable name), split into `--text-secondary-light` and `--text-secondary-dark` (or equivalent naming) rather than compromising dark-theme compliance.
5. Produce and commit the audit output as a `contrast-report.txt` in the plan folder (`pathly/plans/studio-design-polish/contrast-report.txt`) — not in source.

**Key files:**
- `studio/src/renderer/src/theme.ts`

**Leave runnable:** No color regressions. Audit report present.

**Verify:**
- AC-07-1, AC-07-2, AC-07-3, AC-07-4

---

## Open Items

### OPEN: Font bundling method
Is Inter to be bundled as static woff2 files shipped with the Electron app, or loaded via an npm font package (e.g., `@fontsource/inter`)? Both work offline. Architect or builder to decide in Conversation 1.

### OPEN: Focus ring color
Should `--focus-ring` use the existing `--accent` color or a dedicated focus color token? (See S-02.) Default in plan: use `--accent`. If a dedicated token is wanted, PO must supply the color value before Phase 2 is implemented.

### OPEN: FlowWizard Step 1 uniqueness validation
Is the duplicate flow name check synchronous (against in-memory state) or async (against persisted data)? If async, does it block Next or show a deferred warning? Default in plan: non-empty check only (synchronous). PO to clarify.

### ARCH_QUESTION: Contrast audit tooling
What tool or method should be used for the automated contrast audit (AC-07-4)? Options include: axe-core, a custom Node script parsing theme.ts token values, or manual DevTools. This also determines whether a CI gate is added. Direct architect to `/meet architect` before Phase 6 begins.
