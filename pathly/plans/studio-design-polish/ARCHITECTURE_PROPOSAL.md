# Architecture Proposal — studio-design-polish

_Rigor: lite. This is a polish pass — no API changes, no structural redesign._

---

## 1. Scope Overview

This feature touches three layers in a strictly top-down dependency direction:

```
theme.ts (tokens)
     |
     v
CSS variables injected at :root
     |
     v
UI components (Button, Input, IconButton, Sidebar, FlowWizard)
```

No component may introduce a color, size, or motion value that does not trace back to a token in `theme.ts`. The reverse direction — a component defining a value that `theme.ts` then reflects — is prohibited.

---

## 2. Token Layer — theme.ts

### New tokens to add

| Token | Light value | Dark value | Notes |
|---|---|---|---|
| `--font-family-base` | `"Inter", system-ui, sans-serif` | same | Theme-independent |
| `--font-size-base` | `15px` | same | Theme-independent |
| `--focus-ring` | `2px solid var(--accent)` | same | Default to `--accent`; see Open Items |
| `--border` | `1px solid #c0c0d8` | `1px solid #3a3a58` | Derived from surface-adjacent palette |
| `--transition-base` | `150ms ease-out` | same | Theme-independent |

### Design rules

- Typography tokens (`--font-family-base`, `--font-size-base`) carry the same value in both themes. They are defined once in the shared section — do not duplicate per theme unless a future need arises.
- Motion token (`--transition-base`) follows the same rule.
- Border and focus tokens carry per-theme values because they derive from surface colors that differ between themes.
- Adding `--border-subtle` and `--border-strong` is deferred until a component actually requires two distinct border intensities. Do not pre-add unused tokens.

### Token injection

Tokens are exposed as CSS custom properties on `:root` via the existing theme-switching mechanism. No changes to the switching mechanism itself.

---

## 3. Font Bundling — Decision

**Chosen approach: `@fontsource/inter` npm package.**

Rationale:

- The package publishes pre-optimized woff2 subsets for each weight. Importing a single weight (e.g., `@fontsource/inter/400.css`) pulls exactly the files needed — no manual subset work.
- Electron's Vite build pipeline already resolves and bundles npm assets. The font files end up in the output `assets/` directory automatically, with no manual copy step.
- Maintenance is a single `npm update @fontsource/inter` — no managing raw binary files in `assets/fonts/`.
- Offline-first guarantee: `@fontsource` packages contain no CDN references. The woff2 files are local npm artifacts that Vite inlines into the build.

**Rejected alternative: static woff2 files in `assets/fonts/`**

Manual placement of woff2 binaries in source control increases repository size, requires manual updates to track upstream Inter releases, and adds a `@font-face` declaration block that the developer must maintain by hand. No functional advantage over the npm approach.

**Implementation point:** Import the desired Inter weights in `studio/src/renderer/src/main.tsx` or a root CSS entry file — not in `index.html`. This keeps font loading under Vite's asset graph and ensures correct content hashing in production builds.

---

## 4. New Files

### `FlowWizard.validation.ts`

- Location: `studio/src/renderer/src/components/FlowWizard/FlowWizard.validation.ts`
- Pure function module — no React, no side effects.
- Exports a single `validateStep(step: number, values: WizardValues): Record<string, string>` function.
- Returning an empty object means valid. Returning `{ fieldName: "error message" }` means invalid.
- Keeping validation logic in a pure module makes it unit-testable without mounting the wizard component.

### `FieldError.tsx`

- Location: `studio/src/renderer/src/components/ui/FieldError.tsx`
- Shared presentational component. Renders a single error string below a form field.
- Props: `message?: string`. Renders nothing when `message` is undefined or empty.
- Styled via its own CSS module (`FieldError.module.css`) using `--red` and `--font-size-base` tokens — no inline styles.
- Used by `FlowWizard.tsx` only in this feature. Designed to be reusable by any future form component.

---

## 5. Dependency Direction — Enforced Rules

```
theme.ts
  defines tokens

index.html / main.tsx
  imports @fontsource/inter
  applies :root CSS variables from theme

UI components (Button, Input, IconButton, Sidebar, FlowWizard)
  consume var(--token-name)
  MUST NOT hardcode hex, px font sizes, or ms transition values
  MUST NOT add new tokens — escalate to theme.ts first

FlowWizard.validation.ts
  pure logic — no imports from UI layer
  imported by FlowWizard.tsx

FieldError.tsx
  presentational leaf — no state, no context
  imported by FlowWizard.tsx (and future form components)
```

Violations to flag in code review:
- Any `#xxxxxx` color value outside `theme.ts`
- Any `font-size: <px>` outside `theme.ts` or a documented exception
- Any `transition: <value>` that is not `var(--transition-base)` or `0ms`

---

## 6. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Larger base font (15–16px) clips text in fixed-height containers | Medium | Low | Spot-fix affected containers to `min-height`. Do not restructure layout. |
| `--border` token value visually diverges from existing hardcoded values when replaced | Low | Low | Match the existing computed border color when deriving the token value. Verify by screenshot before/after in both themes. |
| `--focus-ring` using `--accent` has insufficient contrast in light theme | Low | Medium | If contrast fails AC-02-3, darken the outline color for light theme only and document in code comment. |
| `@fontsource/inter` import adds unexpected weight variants to the bundle | Low | Low | Import only the specific weight files needed (400, 500, 600). Do not use the barrel import. |
| Reduced-motion rule placement causes specificity conflict with component transitions | Low | Low | Place the `@media (prefers-reduced-motion)` override on `:root` at the same level as the token definition, not inside component CSS modules. |
| FlowWizard validation refactor breaks existing Step 1–2 submit behavior | Medium | Medium | The existing `handleNext()` guard logic must be removed entirely and replaced — not run in parallel — with the new `validateStep()` path. Verify with end-to-end wizard walkthrough after Phase 5. |

---

## 7. Out of Scope

- No changes to the theme-switching mechanism.
- No changes to FlowWizard's step structure, props API, or data model.
- No new design tokens beyond the five listed in section 2.
- No dark-theme typography or sizing changes (tokens are theme-independent for typography).
- Contrast audit tooling (S-07 / Phase 6) is blocked on an ARCH_QUESTION — see `PLAN.md` Open Items. Architecture for that phase is deferred until the architect decides on the audit tool.

---

## 8. Open Architectural Questions

These are carried over from `PLAN.md` for visibility. Do not implement the affected phases until resolved.

**ARCH_QUESTION (S-07):** What tool is used for the automated contrast audit? Options include axe-core, a custom Node script parsing `theme.ts` token values, or manual DevTools. This affects whether a CI gate is added. Direct the architect to `/meet architect` before Phase 6 begins.

**OPEN (S-02):** Should `--focus-ring` use `--accent` or a dedicated focus color token? Default in plan: use `--accent`. Requires PO confirmation if a dedicated token is wanted.

**OPEN (S-01):** Font bundling method is resolved above — `@fontsource/inter`. No further action needed.
