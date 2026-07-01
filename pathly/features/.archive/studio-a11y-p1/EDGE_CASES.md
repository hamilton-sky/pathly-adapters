---
name: Edge Cases
---
# Studio A11y Phase 1 — Edge Cases

---

## EC-1: ConfigForm readOnly chips must not be interactive

**Scenario:** `adapterChipsEl(true)` is called in compact mode (sidebar preview).
**Risk:** If `<button>` is rendered in readOnly mode, it gets tab-focused and Space/Enter fires an event.
**Guard:** readOnly=true renders `<span>` (not a button, not focusable, no role).
**Test:** Inspect compact mode DOM — no `<button>` inside `.adapterChips` when compact=true.

---

## EC-2: useFocusTrap with zero focusable children

**Scenario:** A modal renders with no focusable children (edge case in a loading state).
**Risk:** `itemRefs.current[0]` is null; calling `.focus()` throws.
**Guard:** `useFocusTrap` must check `focusableEls.length > 0` before calling `.focus()` or setting up Tab cycling.
**Test:** Render an empty modal div — no error thrown.

---

## EC-3: Focus restore after modal close when trigger element is removed

**Scenario:** The element that triggered DeleteConfirmModal is removed from the DOM during the delete operation (the item itself gets deleted).
**Risk:** `previousFocus.focus()` throws or silently fails.
**Guard:** `useFocusTrap` checks `previousFocus instanceof HTMLElement && document.contains(previousFocus)` before calling `.focus()`.

---

## EC-4: ContextMenu with a single item

**Scenario:** Context menu is opened for an item that has only one menu option (e.g., "Rename").
**Risk:** ArrowDown from the only item should stay on that item (modulo 1 = 0, which is correct), but developer might accidentally introduce an out-of-bounds index.
**Guard:** Wrap logic `(index + 1) % items.length` handles this correctly — verify manually.

---

## EC-5: Escape key double-handling in NewItemDialog

**Scenario:** After Phase 7, NewItemDialog has both: the existing Escape `useEffect` on `document` AND the `useFocusTrap` keydown listener.
**Risk:** Two listeners fire on Escape — modal closes twice (second call on already-unmounted component → React warning).
**Guard:** `useFocusTrap` listens for Tab/Shift+Tab only; it does NOT intercept Escape. The existing handler in NewItemDialog remains the sole Escape handler.
**Verify:** Confirm `useFocusTrap` keydown only calls `e.preventDefault()` for Tab keys.

---

## EC-6: `--text-disabled` missing from a theme block

**Scenario:** Builder adds the variable to 11 of 12 themes, misses one.
**Risk:** The missing theme falls back to `inherit` (or browser default) — disabled text may look enabled.
**Guard:** Conv 3 verify: `grep -c "text-disabled" studio/src/renderer/src/styles/tokens.css` must return ≥ 12.
