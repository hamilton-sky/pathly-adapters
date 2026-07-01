RESULT: PASS

# Studio A11y Phase 1 — Test Results

Tester: claude-sonnet-4-6
Date: 2026-06-03
Typecheck command: `cd studio && npm run typecheck` (exit 0 — no errors)

---

## Story S1.1: Adapter chips are keyboard-operable switches

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Each adapter chip in ConfigForm (edit mode) renders as `<button type="button" role="switch" aria-checked="true|false">` | PASS | `ConfigForm.tsx` lines 70–83: `<button type="button" role="switch" aria-checked={active ? 'true' : 'false'}>` inside `adapterChipsEl(false)` |
| 2 | Each adapter chip in NewItemDialog renders as `<button type="button" role="switch" aria-checked="true|false">` | PASS | `NewItemDialog.tsx` lines 158–169: same pattern — `<button type="button" role="switch" aria-checked={active ? 'true' : 'false'}>` |
| 3 | `aria-checked` is `"true"` when active, `"false"` when inactive | PASS | Both files: `aria-checked={active ? 'true' : 'false'}` — string literal coercion confirmed at ConfigForm.tsx:74 and NewItemDialog.tsx:162 |
| 4 | Pressing Space or Enter on a chip toggles state (button semantics — onClick fires on Space/Enter) | PASS | Chips are native `<button>` elements with `onClick` — no `onKeyDown` override suppresses default behavior; browser fires `click` on Space/Enter natively |
| 5 | Chips in ConfigForm compact/readOnly mode render as non-interactive `<span>` elements | PASS | `ConfigForm.tsx` lines 57–66: `readOnly` branch renders `<span className={styles.chip}>` with no `tabIndex`, no `onClick`; `compact` prop calls `adapterChipsEl(true)` at line 94 |
| 6 | TypeScript check passes | PASS | `cd studio && npm run typecheck` → exit 0, no errors |

---

## Story S2.1: Modal dialogs announce correctly and trap focus

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | DeleteConfirmModal renders with `role="dialog"` and `aria-modal="true"` on box element | PASS | `DeleteConfirmModal.tsx` lines 25–29: `<div ref={boxRef} role="dialog" aria-modal="true" aria-labelledby="delete-modal-title">` |
| 2 | DeleteConfirmModal has `aria-labelledby` pointing to id on the title `<p>` | PASS | `DeleteConfirmModal.tsx` line 28: `aria-labelledby="delete-modal-title"`; title `<p>` at line 31: `id="delete-modal-title"` |
| 3 | Pressing Escape while DeleteConfirmModal is open calls `onCancel` | PASS | `DeleteConfirmModal.tsx` lines 16–19: `useEffect` adds `keydown` listener; `if (e.key === 'Escape') onCancel()` |
| 4 | Focus is trapped inside DeleteConfirmModal (useFocusTrap applied to boxRef) | PASS | `DeleteConfirmModal.tsx` line 14: `useFocusTrap(boxRef)`; `useFocusTrap.ts` lines 19–38: Tab/Shift+Tab wraps within focusable elements; cleanup at lines 43–47 restores prior focus |
| 5 | NewItemDialog card has `role="dialog"`, `aria-modal="true"`, `aria-labelledby` pointing to header id | PASS | `NewItemDialog.tsx` lines 112–116: `role="dialog" aria-modal="true" aria-labelledby="new-item-dialog-title"`; header div at line 118: `id="new-item-dialog-title"` |
| 6 | TypeScript check passes | PASS | `cd studio && npm run typecheck` → exit 0, no errors |

---

## Story S3.1: Context menu is navigable with arrow keys

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | ContextMenu container has `role="menu"` | PASS | `ContextMenu.tsx` line 76: `<div ref={ref} role="menu" ...>` |
| 2 | Each item button has `role="menuitem"` | PASS | `ContextMenu.tsx` line 81: `role="menuitem"` on each `<button>` |
| 3 | ArrowDown moves focus to next item with wrap | PASS | `ContextMenu.tsx` lines 50–56: `((prev ?? -1) + 1) % items.length` — wraps last→first; calls `itemRefs.current[next]?.focus()` |
| 4 | ArrowUp moves focus to previous item with wrap | PASS | `ContextMenu.tsx` lines 57–63: `((prev ?? 0) - 1 + items.length) % items.length` — wraps first→last; calls `itemRefs.current[next]?.focus()` |
| 5 | Home moves to first, End to last | PASS | `ContextMenu.tsx` lines 64–72: `Home` → `itemRefs.current[0]?.focus()`; `End` → `itemRefs.current[items.length - 1]?.focus()` |
| 6 | Escape still closes menu | PASS | `ContextMenu.tsx` lines 34–36: `handleKeyDown` on document — `if (e.key === 'Escape') onClose()` |

**Additional note — auto-focus on open:** `ContextMenu.tsx` lines 45–47: `useEffect(() => { itemRefs.current[0]?.focus() }, [])` satisfies the edge-case criterion that focus moves to the first item when the menu opens.

---

## Story S4.1: Disabled buttons have predictable appearance without opacity stacking

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `tokens.css` defines `--text-disabled` in every theme block (all 12) | PASS | Grep confirms 12 occurrences: `:root` (line 66), `light` (104), `nord` (142), `mocha` (180), `solarized` (218), `dracula` (256), `rose-pine` (294), `solarized-light` (332), `latte` (370), `paper` (408), `rose-pine-dawn` (446), `mint` (484) |
| 2 | `.pathly-btn-b:disabled` does NOT use `opacity: 0.35` | PASS | `buttons.css`: grep for `opacity` → no matches anywhere in file |
| 3 | `.pathly-btn-b:disabled` uses `color: var(--text-disabled)` and `cursor: not-allowed` | PASS | `buttons.css` lines 41–44: `.pathly-btn-b:disabled { color: var(--text-disabled); cursor: not-allowed; }` |
| 4 | TypeScript check passes | PASS | `cd studio && npm run typecheck` → exit 0, no errors |

---

## Summary

| Story | Criteria | Pass | Fail | Not Covered |
|---|---|---|---|---|
| S1.1 | 6 | 6 | 0 | 0 |
| S2.1 | 6 | 6 | 0 | 0 |
| S3.1 | 6 | 6 | 0 | 0 |
| S4.1 | 4 | 4 | 0 | 0 |
| **Total** | **22** | **22** | **0** | **0** |

All 22 acceptance criteria PASS. TypeScript check passes clean.
