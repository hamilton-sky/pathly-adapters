---
name: Conversation Guide
---
# Studio A11y Phase 1 — Conversation Guide

Split into 3 conversations. Each ends with `npm run typecheck` passing.
After each conversation, **commit your changes** before starting the next.

---

## Conversation 1: Chip toggles → semantic buttons (Phases 0–4)

**Stories delivered:** S1.1

**Prompt to paste:**
```
Read pathly/plans/studio-a11y-p1/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Studio A11y Phase 1 — Conversation 1 (Phases 0–4) from pathly/plans/studio-a11y-p1/IMPLEMENTATION_PLAN.md.

**Before editing anything:** glob/read the live repo to confirm every file path in FEATURE_INDEX.md exists.
Correct any discrepancy between the plan's stated paths and reality before proceeding.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/components/Editor/ConfigForm.tsx` — chip <div> → <button role="switch">
- `studio/src/renderer/src/components/Editor/ConfigForm.module.css` — button reset styles on .chip
- `studio/src/renderer/src/components/NewItemDialog.tsx` — chip <div> → <button role="switch">
- `studio/src/renderer/src/components/NewItemDialog.module.css` — button reset styles on .chip

Scope:
- Phase 0: Run `npm run typecheck` from repo root. Record whether it passes or fails (pre-existing failures are not your responsibility — only errors you introduce are).
- Phase 1: In ConfigForm.tsx, change `adapterChipsEl(readOnly)` so that when readOnly=false the chip renders as `<button type="button" role="switch" aria-checked={active ? 'true' : 'false'}>` and when readOnly=true it renders as `<span>`. Keep `style={chipVars(...)}` — CSS custom properties are an accepted exception per studio CLAUDE.md.
- Phase 2: In ConfigForm.module.css, add button-reset properties and a :focus-visible ring to the `.chip` selector.
- Phase 3: In NewItemDialog.tsx, change the adapter chip `<div>` elements to `<button type="button" role="switch" aria-checked={active ? 'true' : 'false'}>`. Add `title={active ? \`Remove \${adapter}\` : \`Add \${adapter}\`}`.
- Phase 4: In NewItemDialog.module.css, add the same button-reset and :focus-visible styles to `.chip`.

Architectural rules:
- No inline `style={{}}` props beyond CSS custom properties (which were already there)
- Every `<button>` must have `type="button"`
- Do NOT touch modals, ContextMenu, tokens.css, or buttons.css yet

Do NOT touch useFocusTrap, DeleteConfirmModal, ContextMenu, tokens.css, or buttons.css.

After all phases: run `npm run typecheck` — it must pass with no new errors.
Also run: `grep -rn "<div.*onClick" studio/src/renderer/src/components/Editor/ConfigForm.tsx studio/src/renderer/src/components/NewItemDialog.tsx` — the adapter chip divs must be gone (zero matches for chip divs with onClick).
After done, update pathly/plans/studio-a11y-p1/PROGRESS.md phases 0–4 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** ConfigForm and NewItemDialog adapter chips are keyboard-operable `<button role="switch">` elements with correct ARIA states. TypeScript clean.
**Files touched:** `ConfigForm.tsx`, `ConfigForm.module.css`, `NewItemDialog.tsx`, `NewItemDialog.module.css`

---

## Conversation 2: Modal ARIA + focus trap (Phases 5–7)

**Stories delivered:** S2.1

**Prompt to paste:**
```
Read pathly/plans/studio-a11y-p1/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Studio A11y Phase 1 — Conversation 2 (Phases 5–7) from pathly/plans/studio-a11y-p1/IMPLEMENTATION_PLAN.md.

**Prerequisite:** Conversation 1 must be complete (check PROGRESS.md phases 0–4 are DONE).

**Before editing anything:** glob/read the live repo to confirm every file path below exists. Correct any discrepancy before proceeding.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/hooks/useFocusTrap.ts` — CREATE: shared focus-trap hook
- `studio/src/renderer/src/components/sidebar/shared/DeleteConfirmModal.tsx` — add dialog ARIA + Escape + focus trap
- `studio/src/renderer/src/components/NewItemDialog.tsx` — add dialog ARIA to card element + focus trap

Scope:
- Phase 5: CREATE `studio/src/renderer/src/hooks/useFocusTrap.ts`. The hook signature is `useFocusTrap(ref: RefObject<HTMLElement | null>): void`. On mount: (a) record `previousFocus = document.activeElement`; (b) add a keydown listener on `document` that intercepts Tab and Shift+Tab to cycle focus within all focusable children of `ref.current`; (c) focus the first focusable child immediately. On cleanup: remove the listener and restore `previousFocus.focus()` (if it has `.focus()`). Focusable selector: `'button:not(:disabled),[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex]:not([tabindex="-1"])'`.
- Phase 6: In DeleteConfirmModal.tsx — (a) import useEffect, useRef, useFocusTrap; (b) add `boxRef = useRef<HTMLDivElement>(null)` + call `useFocusTrap(boxRef)`; (c) add useEffect for Escape key calling onCancel; (d) add `id="delete-modal-title"` to the title `<p>`; (e) add `ref={boxRef} role="dialog" aria-modal="true" aria-labelledby="delete-modal-title"` to the `.modalBox` div.
- Phase 7: In NewItemDialog.tsx — (a) import useFocusTrap; (b) add `cardRef = useRef<HTMLDivElement>(null)` + call `useFocusTrap(cardRef)`; (c) add `id="new-item-dialog-title"` to the `.header` div; (d) add `ref={cardRef} role="dialog" aria-modal="true" aria-labelledby="new-item-dialog-title"` to the `.card` div. Do NOT add a second Escape handler — one already exists.

Architectural rules:
- useFocusTrap must be in `studio/src/renderer/src/hooks/` (not a component-local file)
- No inline `style={{}}` props introduced
- Follow studio CLAUDE.md: every <button> has type="button"

Do NOT touch ConfigForm, ContextMenu, tokens.css, or buttons.css.

After all phases: run `npm run typecheck` — it must pass with no new errors.
After done, update pathly/plans/studio-a11y-p1/PROGRESS.md phases 5–7 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** `useFocusTrap.ts` exists. DeleteConfirmModal and NewItemDialog card have full dialog ARIA; focus traps within them; Escape closes DeleteConfirmModal.
**Files touched:** `useFocusTrap.ts` (new), `DeleteConfirmModal.tsx`, `NewItemDialog.tsx`

---

## Conversation 3: ContextMenu ARIA + disabled tokens (Phases 8–10)

**Stories delivered:** S3.1, S4.1

**Prompt to paste:**
```
Read pathly/plans/studio-a11y-p1/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Studio A11y Phase 1 — Conversation 3 (Phases 8–10) from pathly/plans/studio-a11y-p1/IMPLEMENTATION_PLAN.md.

**Prerequisite:** Conversations 1 and 2 must be complete (check PROGRESS.md phases 0–7 are DONE).

**Before editing anything:** glob/read to confirm every path exists. For tokens.css, glob `studio/src/renderer/src/styles/` to confirm the exact filename.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/components/ui/ContextMenu.tsx` — role=menu, role=menuitem, arrow-key nav
- `studio/src/renderer/src/styles/tokens.css` — add --text-disabled to every theme block
- `studio/src/renderer/src/styles/buttons.css` — replace opacity:0.35 with var(--text-disabled)

Scope:
- Phase 8: In ContextMenu.tsx — (a) add `role="menu"` to the outer `<div ref={ref}>`; (b) add `role="menuitem"` and `tabIndex={-1}` to each item `<button>`; (c) add `itemRefs = useRef<(HTMLButtonElement | null)[]>([])` and assign each button via `ref={(el) => { itemRefs.current[i] = el }}`; (d) add `useEffect(() => { itemRefs.current[0]?.focus() }, [])` to focus the first item on open; (e) add `onKeyDown` to the container div handling ArrowDown (next, wrap), ArrowUp (prev, wrap), Home (first), End (last) — use `setHoveredIndex` + `.focus()` to keep visual highlight and real focus in sync. Keep all existing inline styles and Escape logic unchanged.
- Phase 9: Read tokens.css in full to identify every theme block. Add `--text-disabled: <value>` to each theme. Dark themes: use approximately `#4A5568`. Light themes: use approximately `#94A3B8`. Exact values may vary — aim for visually muted but not invisible.
- Phase 10: In buttons.css, find `.pathly-btn-b:disabled` and replace `opacity: 0.35; cursor: not-allowed;` with `color: var(--text-disabled); cursor: not-allowed;`. Do NOT touch `IconButton.module.css` (that is Phase 2 scope).

Architectural rules:
- ContextMenu uses inline styles throughout (pre-existing pattern) — do not add new inline styles for the new ARIA/focus behavior
- Do NOT add a CSS module to ContextMenu as part of this change
- Follow studio CLAUDE.md: every <button> has type="button"

Do NOT touch ConfigForm, NewItemDialog, DeleteConfirmModal, or useFocusTrap.

After all phases: run `npm run typecheck` — it must pass with no new errors.
Also verify: `grep -n "opacity: 0.35" studio/src/renderer/src/styles/buttons.css` — must return no matches.
Also verify: `grep -c "text-disabled" studio/src/renderer/src/styles/tokens.css` — must return 12 or more (one per theme block).
After done, update pathly/plans/studio-a11y-p1/PROGRESS.md phases 8–10 to DONE and set Status to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** ContextMenu has `role="menu"` container and `role="menuitem"` items with full arrow-key navigation. `tokens.css` has `--text-disabled` in all 12 themes. `buttons.css` disabled state uses the token. TypeScript clean.
**Files touched:** `ContextMenu.tsx`, `tokens.css`, `buttons.css`
