# TEST_FAILURES — studio-design-polish

Generated: 2026-05-19

---

## FAIL 1 — AC-01-2: fontSizeBase is 14px, not 15–16px

**Story:** S-01 — Readable Typography Baseline
**Criterion:** Base font size is 15px or 16px (configurable via token).

**What was expected:** `fontSizeBase` token value is `'15px'` or `'16px'` in `theme.ts`.

**What actually happened:** `fontSizeBase` is `'14px'` in both `darkTheme` and `lightTheme` in `theme.ts` (lines 38 and 63).

**File:** `studio/src/renderer/src/theme.ts`, lines 38, 63

---

## FAIL 2 — AC-06-3: No live clearing of errors after field is corrected

**Story:** S-06 — FlowWizard Inline Validation and Step Progress
**Criterion:** Error messages clear when the field becomes valid (live validation after first blur or submit attempt).

**What was expected:** After a validation error is displayed on a field, correcting the field value causes the error to disappear (either on change or on blur) without requiring the user to press Next again.

**What actually happened:** Validation only runs inside `handleNext()` in `FlowWizard.tsx`. There is no `onChange` or `onBlur` handler that re-runs `validateStep()` and clears `stepErrors` for the current step. The error persists in `stepErrors[step]` until the user presses Next successfully and advances to the next step. If the user stays on the same step after correcting the field, the error text remains visible.

**File:** `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx`, `handleNext()` (lines 56–66); no onChange/onBlur validation path exists.

---

## Additional observation (not a FAIL at this rigor level)

**AC-03-2 (panelStyles addBtn border):** `panelStyles.ts` line 74 uses `border: \`1px dashed ${t.bgSurface1}\`` for `addBtn`. This uses a theme token value (not a raw hex literal), but `t.bgSurface1` is not the `--border` or `--border-subtle` token. A comment in the file marks it as an intentional divider. At lite rigor this passes the "no hardcoded hex" grep check, but a stricter read of AC-03-2 may flag it.

**AC-02-2 (Sidebar.module.css focus-visible):** Sidebar CSS uses `outline: 2px solid var(--accent, #89b4fa)` with a `#89b4fa` fallback (not `var(--focus-ring)`). The Button/Input/IconButton components correctly use `var(--focus-ring)` via `ui.module.css`. Sidebar is not listed in AC-02-2's scope (only Button, Input, IconButton), so this does not fail AC-02-2, but it is an inconsistency worth noting.
