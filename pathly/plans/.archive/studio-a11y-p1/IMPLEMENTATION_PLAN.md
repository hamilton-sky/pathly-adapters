---
name: Implementation Plan
---
# Studio A11y Phase 1 — Implementation Plan

## Overview

Four targeted WCAG 2.1 AA fixes in the Pathly Studio Electron/React frontend. All changes
are in `studio/src/renderer/src/`. No new npm dependencies. No visual changes intended.
TypeScript `npm run typecheck` must pass after every conversation.

## Layer Architecture

```
studio/src/renderer/src/
  components/
    Editor/ConfigForm.tsx          ← Conv 1: chip div → button
    Editor/ConfigForm.module.css   ← Conv 1: button reset styles
    NewItemDialog.tsx              ← Conv 1 + Conv 2: chips + modal ARIA
    NewItemDialog.module.css       ← Conv 1: button reset styles
    sidebar/shared/
      DeleteConfirmModal.tsx       ← Conv 2: full dialog ARIA
    ui/
      ContextMenu.tsx              ← Conv 3: menu ARIA + arrow keys
  hooks/
    useFocusTrap.ts                ← Conv 2: NEW shared hook
  styles/
    tokens.css                     ← Conv 3: --text-disabled per theme
    buttons.css                    ← Conv 3: disabled uses token
```

---

## Phases

### Phase 0: Pre-flight   ← Conversation: 1

**File:** (no file changes — verification only)
**Done when:** `npm run typecheck` exits 0 with no new errors on the unmodified branch.
**Details:** Run `npm run typecheck` from repo root before touching any file. Record whether
the baseline passes. If it fails, note the pre-existing errors and proceed — only errors
*introduced by this feature* are in scope.
**Verify:** `npm run typecheck`

---

### Phase 1: ConfigForm chip → `button[role="switch"]`   ← Conversation: 1

**File:** `studio/src/renderer/src/components/Editor/ConfigForm.tsx`
**Done when:** The `adapterChipsEl` function returns `<button>` elements when `readOnly` is
false and `<span>` elements when `readOnly` is true; `aria-checked` reflects active state.
**Delivers stories:** S1.1 (partial — ConfigForm half)
**Depends on:** Phase 0
**Enables:** Phase 2 (CSS), S1.1 acceptance criteria for ConfigForm
**Details:**
- In `adapterChipsEl(readOnly: boolean)`, branch on `readOnly`:
  - `readOnly = false` → render `<button type="button" role="switch" aria-checked={active ? 'true' : 'false'} className={styles.chip} style={chipVars(active, meta)} onClick={() => toggleAdapter(adapter, !active)} title={active ? \`Remove \${adapter}\` : \`Add \${adapter}\`}>`
  - `readOnly = true` → render `<span className={styles.chip} style={chipVars(active, meta)} title={adapter}>` (no onClick, no role, not focusable)
- Remove `data-label` attr (it was only a testing hook; the accessible name now comes from `title` / `aria-label`)
- Keep `style={chipVars(...)}` — it sets CSS custom properties, which is the accepted exception in studio CLAUDE.md
**Verify:** `npm run typecheck`

---

### Phase 2: ConfigForm chip CSS button reset   ← Conversation: 1

**File:** `studio/src/renderer/src/components/Editor/ConfigForm.module.css`
**Done when:** `.chip` selector (when rendered as `<button>`) shows no browser-default button
border, outline-on-click, or white background; cursor is pointer; focus-visible ring appears.
**Delivers stories:** S1.1 (visual correctness for keyboard focus)
**Depends on:** Phase 1
**Enables:** S1.1 visual acceptance
**Details:**
- Add to the `.chip` rule: `background: none; border: none; cursor: pointer; font: inherit; padding: 0; text-align: left;`
- Add `:focus-visible` rule on `.chip`: `outline: var(--focus-ring); outline-offset: 2px;`
- The `<span>` (readOnly) variant inherits these gracefully — reset properties are harmless on spans
**Verify:** `npm run typecheck`

---

### Phase 3: NewItemDialog chip → `button[role="switch"]`   ← Conversation: 1

**File:** `studio/src/renderer/src/components/NewItemDialog.tsx`
**Done when:** The three adapter chip `<div>` elements in the skill form are `<button type="button" role="switch" aria-checked={active ? 'true' : 'false'}>` elements.
**Delivers stories:** S1.1 (NewItemDialog half)
**Depends on:** Phase 0
**Enables:** S1.1 fully complete for both components
**Details:**
- Inside the `{ADAPTER_OPTIONS.map(...)}` block (skill section), change the outer `<div>` to
  `<button type="button" role="switch" aria-checked={active ? 'true' : 'false'} className={styles.chip} style={chipVars(active, meta)} onClick={() => toggleAdapter(adapter)}>`
- Keep `style={chipVars(...)}` as-is
- Add `title={active ? \`Remove \${adapter}\` : \`Add \${adapter}\`}` for the accessible name
**Verify:** `npm run typecheck`

---

### Phase 4: NewItemDialog chip CSS button reset   ← Conversation: 1

**File:** `studio/src/renderer/src/components/NewItemDialog.module.css`
**Done when:** `.chip` button reset applied; no browser default button styles visible.
**Delivers stories:** S1.1 (visual correctness)
**Depends on:** Phase 3
**Details:** Same additions as Phase 2 — `background: none; border: none; cursor: pointer; font: inherit; padding: 0;` and `:focus-visible` rule.
**Verify:** `npm run typecheck`

---

### Phase 5: `useFocusTrap` hook   ← Conversation: 2

**File:** `studio/src/renderer/src/hooks/useFocusTrap.ts` (CREATE)
**Done when:** File exists and exports `useFocusTrap(ref: RefObject<HTMLElement>): void`. The
hook traps Tab/Shift+Tab within focusable children; restores focus to `document.activeElement`
at mount time when the hook cleans up.
**Delivers stories:** S2.1 (shared infrastructure)
**Depends on:** Conv 1 complete
**Enables:** Phases 6 and 7 (both modals use this hook)
**Details:**
```
useFocusTrap(ref: RefObject<HTMLElement | null>): void
  - On mount: record previousFocus = document.activeElement
  - Build focusable selector:
    'button:not(:disabled),[href],input:not(:disabled),select:not(:disabled),
     textarea:not(:disabled),[tabindex]:not([tabindex="-1"])'
  - Add keydown listener to document:
    - Tab (no Shift): if focus is on last focusable, move to first
    - Shift+Tab: if focus is on first focusable, move to last
    - All other keys: do nothing (let event propagate)
  - On cleanup: restore focus to previousFocus (if it has a .focus() method)
```
- No external dependencies — plain DOM APIs only
- Export as named export: `export function useFocusTrap(...)`
**Verify:** `npm run typecheck`

---

### Phase 6: DeleteConfirmModal ARIA + focus trap   ← Conversation: 2

**File:** `studio/src/renderer/src/components/sidebar/shared/DeleteConfirmModal.tsx`
**Done when:** The `.modalBox` div has `role="dialog"`, `aria-modal="true"`, `aria-labelledby`
pointing to a title id; Escape calls `onCancel`; `useFocusTrap` is active on the box ref.
**Delivers stories:** S2.1 (DeleteConfirmModal half)
**Depends on:** Phase 5
**Enables:** S2.1 acceptance criteria for DeleteConfirmModal
**Details:**
- Add `import { useEffect, useRef } from 'react'` and `import { useFocusTrap } from '../../../hooks/useFocusTrap'`
- Add `const boxRef = useRef<HTMLDivElement>(null)` and call `useFocusTrap(boxRef)`
- Add `useEffect` for Escape: `document.addEventListener('keydown', onKey)` where `onKey = (e) => { if (e.key === 'Escape') onCancel() }`; clean up in return
- Add `id="delete-modal-title"` to the title `<p>` element
- Add to the `.modalBox` div: `ref={boxRef} role="dialog" aria-modal="true" aria-labelledby="delete-modal-title"`
**Verify:** `npm run typecheck`

---

### Phase 7: NewItemDialog modal ARIA   ← Conversation: 2

**File:** `studio/src/renderer/src/components/NewItemDialog.tsx`
**Done when:** The `.card` div has `role="dialog"`, `aria-modal="true"`, and `aria-labelledby`
pointing to a unique id on the `.header` div; `useFocusTrap` is active on the card ref.
**Delivers stories:** S2.1 (NewItemDialog half)
**Depends on:** Phase 5
**Enables:** S2.1 fully complete for both modals
**Details:**
- Add `import { useFocusTrap } from '../hooks/useFocusTrap'`
- Add `const cardRef = useRef<HTMLDivElement>(null)` and call `useFocusTrap(cardRef)`
- Add `id="new-item-dialog-title"` to the `.header` div
- Add to the `.card` div: `ref={cardRef} role="dialog" aria-modal="true" aria-labelledby="new-item-dialog-title"`
- Do NOT add a second Escape handler — the existing `useEffect` in the component already handles Escape
- `inputRef.current?.focus()` at mount already fires the first focus; `useFocusTrap` then takes over tab cycling
**Verify:** `npm run typecheck`

---

### Phase 8: ContextMenu ARIA + arrow keys   ← Conversation: 3

**File:** `studio/src/renderer/src/components/ui/ContextMenu.tsx`
**Done when:** The container `<div>` has `role="menu"`; each item `<button>` has `role="menuitem"` and `tabIndex={-1}`; ArrowDown/Up/Home/End move focus between items; first item is focused on open.
**Delivers stories:** S3.1
**Depends on:** Conv 2 complete
**Enables:** S3.1 acceptance criteria
**Details:**
- Add `role="menu"` to the outer `<div ref={ref}>` container
- Add `role="menuitem"` and `tabIndex={-1}` to each item `<button>`
- Create `itemRefs = useRef<(HTMLButtonElement | null)[]>([])` and assign each button ref via `ref={(el) => { itemRefs.current[i] = el }}`
- Add `useEffect` that focuses `itemRefs.current[0]` when the menu mounts (replaces hover-based focus)
- Add `onKeyDown` to the container div:
  ```
  ArrowDown: move to (hoveredIndex + 1) % items.length; call .focus()
  ArrowUp: move to (hoveredIndex - 1 + items.length) % items.length; call .focus()
  Home: move to 0
  End: move to items.length - 1
  ```
  Use `setHoveredIndex` to keep the visual highlight in sync with keyboard focus
- Keep Escape handler in the existing `document.addEventListener` useEffect (already works)
- Keep all existing inline styles unchanged (pre-existing pattern; CSS module refactor is out of scope)
**Verify:** `npm run typecheck`

---

### Phase 9: `--text-disabled` CSS variable in tokens   ← Conversation: 3

**File:** `studio/src/renderer/src/styles/tokens.css`
**Done when:** Every theme block in `tokens.css` includes a `--text-disabled` property with a
value appropriate for that theme's surface color.
**Delivers stories:** S4.1 (partial — token definition)
**Depends on:** Conv 2 complete
**Details:**
- Read `tokens.css` first to identify every theme block (dark default `:root`, light, nord,
  mocha, solarized-dark, dracula, rose-pine, solarized-light, latte, paper, rose-pine-dawn, mint — 12 themes)
- For each dark theme add approximately: `--text-disabled: #4A5568;` (muted slate, distinct from background)
- For each light theme add approximately: `--text-disabled: #94A3B8;` (slate-400, reads as clearly subdued)
- Exact values may vary per theme — aim for "clearly muted but not invisible"
**Verify:** `npm run typecheck`

---

### Phase 10: `buttons.css` disabled → token   ← Conversation: 3

**File:** `studio/src/renderer/src/styles/buttons.css`
**Done when:** `.pathly-btn-b:disabled` no longer uses `opacity: 0.35`; uses `color: var(--text-disabled)` and `cursor: not-allowed` instead.
**Delivers stories:** S4.1
**Depends on:** Phase 9
**Enables:** S4.1 fully complete
**Details:**
- Replace `.pathly-btn-b:disabled { opacity: 0.35; cursor: not-allowed; }` with:
  ```css
  .pathly-btn-b:disabled {
    color: var(--text-disabled);
    cursor: not-allowed;
  }
  ```
- Do NOT change `IconButton.module.css` disabled styles (Phase 2 scope, not this feature)
**Verify:** `npm run typecheck`

---

## Prerequisites
- `studio/src/renderer/src/hooks/` directory exists (confirmed: contains `usePlanConversations.ts`)
- `studio/src/renderer/src/styles/tokens.css` exists (verify path at Conv 3 start)

## Key Decisions
- **`style={chipVars(...)}`** — keeping it as-is; it sets CSS custom properties, the accepted inline-style exception in studio CLAUDE.md; converting to `data-` attributes is a separate refactor
- **`useFocusTrap` as a shared hook** — DeleteConfirmModal and NewItemDialog both use it; one hook, no duplication
- **WCAG exemption for disabled elements** — WCAG 2.1 SC 1.4.3 explicitly exempts disabled UI components from minimum contrast; `--text-disabled` is a UX floor, not a compliance requirement
- **ContextMenu keeps inline styles** — pre-existing pattern; CSS module extraction is out of scope
