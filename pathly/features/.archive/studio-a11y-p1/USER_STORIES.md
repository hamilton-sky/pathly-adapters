---
name: User Stories
---
# Studio A11y Phase 1 — User Stories

## Context

Pathly Studio's interactive elements — adapter chip toggles, modals, and the context menu — are
inaccessible to keyboard and screen-reader users. Chips are `<div onClick>` elements with no
semantic role. Modals lack `role="dialog"` and focus trapping. The context menu has no arrow-key
navigation. This feature brings these four component groups to WCAG 2.1 AA compliance with no
visual changes and no new dependencies.

---

## Stories

### Story S1.1: Adapter chips are keyboard-operable switches

**As a** keyboard user, **I want** adapter chips in ConfigForm and NewItemDialog to be
focusable and togglable with Space/Enter, **so that** I can enable and disable adapters
without a mouse.

**Acceptance Criteria:**
- [ ] Each adapter chip in ConfigForm (edit mode) renders as `<button type="button" role="switch" aria-checked="true|false">`
- [ ] Each adapter chip in NewItemDialog renders as `<button type="button" role="switch" aria-checked="true|false">`
- [ ] `aria-checked` is `"true"` when the adapter is active and `"false"` when inactive
- [ ] Pressing Space or Enter on a chip toggles its active state
- [ ] Chips in ConfigForm compact/readOnly mode render as non-interactive `<span>` elements (not buttons)
- [ ] TypeScript check passes: `npm run typecheck`

**Edge Cases:**
- readOnly chips must not be focusable or respond to keyboard events
- All three adapters (claude, codex, copilot) must be individually togglable

**Delivered by:** Phases 1–4 → Conversation 1

---

### Story S2.1: Modal dialogs announce correctly and trap focus

**As a** screen reader or keyboard user, **I want** modal dialogs to be properly announced
and to trap focus inside them, **so that** I cannot accidentally navigate outside a modal.

**Acceptance Criteria:**
- [ ] DeleteConfirmModal renders with `role="dialog"` and `aria-modal="true"` on the box element
- [ ] DeleteConfirmModal has `aria-labelledby` pointing to a unique id on the title `<p>`
- [ ] Pressing Escape while DeleteConfirmModal is open calls `onCancel`
- [ ] Focus is trapped inside DeleteConfirmModal: Tab/Shift+Tab cycles only within the modal
- [ ] NewItemDialog card element has `role="dialog"`, `aria-modal="true"`, and `aria-labelledby` pointing to the header element's id
- [ ] TypeScript check passes: `npm run typecheck`

**Edge Cases:**
- Focus must restore to the element that triggered the modal when the modal closes
- If the modal has only two focusable elements (Cancel + Delete), Tab from Delete wraps back to Cancel

**Delivered by:** Phases 5–7 → Conversation 2

---

### Story S3.1: Context menu is navigable with arrow keys

**As a** keyboard user, **I want** to navigate ContextMenu items using Up/Down arrow keys,
**so that** I can use standard ARIA menu keyboard conventions.

**Acceptance Criteria:**
- [ ] ContextMenu container renders with `role="menu"`
- [ ] Each menu item button renders with `role="menuitem"`
- [ ] ArrowDown moves focus to the next item; wraps from last to first
- [ ] ArrowUp moves focus to the previous item; wraps from first to last
- [ ] Home moves focus to the first item; End moves focus to the last item
- [ ] Pressing Escape still closes the menu (pre-existing behavior preserved)

**Edge Cases:**
- Menu with a single item: ArrowDown and ArrowUp both stay on that item (no wrap needed)
- Focus must move to the first item automatically when the menu opens

**Delivered by:** Phase 8 → Conversation 3

---

### Story S4.1: Disabled buttons have predictable appearance without opacity stacking

**As a** user across all 12 Pathly themes, **I want** disabled buttons to use an explicit
disabled color token instead of opacity, **so that** disabled state is visually consistent
and not subject to compounding opacity artifacts.

**Acceptance Criteria:**
- [ ] `tokens.css` defines `--text-disabled` in every theme block (all 12 themes)
- [ ] `.pathly-btn-b:disabled` in `buttons.css` no longer uses `opacity: 0.35`
- [ ] `.pathly-btn-b:disabled` uses `color: var(--text-disabled)` and `cursor: not-allowed`
- [ ] TypeScript check passes: `npm run typecheck`

**Edge Cases:**
- The `--text-disabled` value per theme must provide at least minimal visual distinction
  from the enabled button color (roughly 2:1 contrast vs background — WCAG exempts disabled
  elements from minimum contrast, so this is a UX floor, not a compliance floor)

**Delivered by:** Phases 9–10 → Conversation 3
