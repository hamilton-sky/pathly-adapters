---
name: Architecture Proposal
---
# Studio A11y Phase 1 — Architecture Proposal

## 1. `useFocusTrap` Hook Design

### Location
`studio/src/renderer/src/hooks/useFocusTrap.ts`

Rationale: the `hooks/` directory already exists with three custom hooks. No new folder needed.

### Signature
```ts
export function useFocusTrap(ref: RefObject<HTMLElement | null>): void
```

### Behaviour contract
- **On mount:** stores `document.activeElement`, then queries all focusable children within `ref.current`, then focuses the first one.
- **During life:** a single `keydown` listener on `document` intercepts Tab and Shift+Tab, cycling focus within the focusable set. All other keys pass through unmodified.
- **On cleanup:** removes the listener, restores focus to the previously stored element (if it's still in the document).

### Why `document` listener instead of on-element
A `keydown` listener on the modal container div can miss events when focus is inside a nested component. Listening on `document` with `useCapture` or in the bubble phase ensures we catch all Tab presses regardless of which child has focus.

### Why not a library (focus-trap, @radix-ui/react-focus-trap)
No new dependencies is an explicit requirement. The implementation is ~25 lines and covers the two modals in scope. A library would be warranted if we had 10+ modal types.

---

## 2. `role="switch"` for Chip Toggles

### Chosen pattern
```tsx
<button type="button" role="switch" aria-checked={active ? 'true' : 'false'}>
  <span className={styles.chipDot} />
  {adapter}
</button>
```

### Why `role="switch"` and not `role="checkbox"`
`role="switch"` communicates binary on/off state (enabled/disabled adapter). `role="checkbox"` implies selection within a group. Screen readers announce switches as "on/off" which better matches the chip's meaning.

### Why not `<input type="checkbox">`
The existing visual design (colored dot chip) is not a standard checkbox. Replacing with a native checkbox would require significant visual restyling. `<button role="switch">` achieves semantic correctness without restyling.

### readOnly variant
When in compact display mode, chips are informational only. They render as `<span>` — no role, not focusable. This avoids announcing read-only state information as interactive controls.

---

## 3. ContextMenu Keyboard Navigation

### Chosen approach
Use `itemRefs` array + imperative `.focus()` calls. This is the standard ARIA pattern for `role="menu"`:
- `tabIndex={-1}` on all items (they are not in the natural Tab order)
- Arrow keys move focus imperatively
- `role="menu"` with `role="menuitem"` children

### Why not a roving tabindex
Roving tabindex (where only the currently-focused item has `tabIndex=0`) is the alternative. It requires updating tabIndex on every keypress. Since we're already calling `.focus()`, roving tabindex adds complexity without benefit for this use case.

### Visual hover sync
`setHoveredIndex` is called alongside `.focus()` on keyboard nav, keeping the visual highlight state consistent with keyboard focus.

---

## 4. Disabled Button Token

### Problem with `opacity: 0.35`
Opacity applies to the entire element including its background. If the parent has a different background, the blended result is unpredictable. Stacking opacity effects (parent + child) compounds this.

### Solution
Define `--text-disabled` per theme as an explicit hex value. Disabled buttons get `color: var(--text-disabled)` only — no opacity modifier.

### WCAG note
WCAG 2.1 SC 1.4.3 explicitly exempts inactive (disabled) UI components from contrast requirements. `--text-disabled` is chosen for visual clarity, not compliance.
