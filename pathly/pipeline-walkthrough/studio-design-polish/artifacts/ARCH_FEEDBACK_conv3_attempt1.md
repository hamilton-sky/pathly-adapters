# ARCH_FEEDBACK — studio-design-polish (conv 3)

Reviewer: adversarial-reviewer
Date: 2026-05-19

---

## Violations

### ARCH-01 — FieldError.tsx: CSS module absent; inline style with useTheme() used instead

**File:** `studio/src/renderer/src/components/ui/FieldError.tsx`
**Rule:** ARCHITECTURE_PROPOSAL.md §4 — "Styled via its own CSS module (`FieldError.module.css`) using `--red` and `--font-size-base` tokens only — no inline styles."
**Evidence:**
```
import { useTheme } from '../../useTheme'
...
const t = useTheme()
...
<span style={{ color: t.red, fontSize: 'var(--font-size-sm)', marginTop: '4px', display: 'block' }}>
```
No `FieldError.module.css` exists anywhere under `studio/src/renderer/src/components/ui/`.

The component uses `useTheme()` (a React context call) and applies inline styles. The ARCH contract mandates a pure presentational leaf with a CSS module — no context access, no inline styles.

This is not a style preference. `useTheme()` makes FieldError context-dependent, breaking its "presentational leaf" contract and making it unrenderable outside a theme provider in tests.

---

### ARCH-02 — theme.ts: `--focus-ring` hardcodes hex values instead of `var(--accent)`

**File:** `studio/src/renderer/src/theme.ts` lines 41, 64
**Rule:** ARCHITECTURE_PROPOSAL.md §2 token table — `--focus-ring` value specified as `2px solid var(--accent)`.
**Evidence:**
```
focusRing: '2px solid #A78BFA',   // line 41 — darkTheme
focusRing: '2px solid #7C3AED',   // line 64 — lightTheme
```
The ARCH table explicitly lists the value as `2px solid var(--accent)`. The implementation substitutes the current accent hex directly. This breaks the cross-reference: if the accent color is ever updated in theme.ts, `focusRing` will diverge silently.

---

### ARCH-03 — theme.ts: `--font-size-base` token value diverges from ARCH-specified `15px`

**File:** `studio/src/renderer/src/theme.ts` lines 38, 61
**Rule:** ARCHITECTURE_PROPOSAL.md §2 token table — `--font-size-base` value specified as `15px`.
**Evidence:**
```
fontSizeBase: '14px',   // line 38 — darkTheme
fontSizeBase: '14px',   // line 61 — lightTheme
```
The ARCH mandates `15px`. The implementation ships `14px`. Either the ARCH was overridden by a design decision and the document was not updated, or this is an implementation error. The discrepancy must be resolved — either update ARCH or update the value — before this can pass review.

---

## Warnings (non-blocking)

- `studio/src/renderer/src/components/FlowWizard/FlowWizard.styles.ts:128` — `fontSize: '11px'` on `stateTag` style — allowed per the documented 11px label exception. No action needed, but the exception count is growing; consider adding a `--font-size-xs` token if more use-cases appear.

---

## Pass

- FlowWizard.validation.ts: pure module, zero imports. Clean.
- FlowWizard.tsx handleNext: single path through validateStep(). No parallel guard. Clean.
- main.tsx: @fontsource/inter 400/500/600 imported correctly, not in index.html. Clean.
- theme.ts: all five new token fields present in both themes and injected in App.tsx. Clean.
- No raw `ms` transition values introduced. Clean.
- No hardcoded hex introduced in UI components (all color references use `t.fieldName` from theme object). Clean.
