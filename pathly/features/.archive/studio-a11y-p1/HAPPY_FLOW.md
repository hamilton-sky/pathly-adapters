---
name: Happy Flow
---
# Studio A11y Phase 1 — Happy Flow

## Persona
A keyboard-only developer using Pathly Studio with a screen reader (NVDA/VoiceOver).

---

## Golden Path: Create a new skill and configure it

1. **User opens the sidebar** and presses Tab to reach the "New Skill" button.
2. **Opens NewItemDialog** — screen reader announces "New Skill, dialog". Focus lands on the Name input (useFocusTrap focuses the first focusable element).
3. **User types** a skill name and Tab to Description. Tab cycles within the dialog only.
4. **User reaches the Adapters section.** Screen reader announces each chip as "claude, switch, not checked". User presses Space — announces "claude, switch, checked". Repeats for codex.
5. **User presses Tab to reach Cancel / Create.** Presses Enter on Create. Dialog closes. Focus returns to the triggering element.

---

## Golden Path: Right-click context menu on a sidebar item

1. **User invokes the context menu** (Shift+F10 or application key). Menu appears. Screen reader announces "context menu" and focus jumps to the first item.
2. **User presses ArrowDown** — focus moves to the next item, screen reader reads the item label.
3. **User presses ArrowUp** — focus moves back. Wrapping at boundaries works.
4. **User presses Enter** on their chosen action. Menu closes.
5. **User presses Escape instead.** Menu closes immediately; focus returns to the sidebar item.

---

## Golden Path: Delete confirmation modal

1. **Delete confirmation appears.** Screen reader announces "Delete [item name]?, dialog". Focus lands on Cancel.
2. **User presses Tab** — moves to Delete. Pressing Tab again wraps back to Cancel (only two focusable elements).
3. **User presses Space on Delete** — confirm action fires. Modal closes.
4. **Alternative: user presses Escape** — calls onCancel. Modal closes.

---

## After all three conversations

- `npm run typecheck` passes
- No `<div onClick>` on adapter chips
- No modals missing `role="dialog"`
- ContextMenu reachable and navigable from keyboard alone
