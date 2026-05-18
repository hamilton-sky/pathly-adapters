# Review Failures — studio-v2 conversation 7

## Context

Re-review after builder fix pass targeting focus-visible violations.

---

## Violations

### V1 — Button.tsx:59 — focus-visible contract — inline `outline: 'none'` overrides CSS `:focus-visible` rule

`studio/src/renderer/src/components/ui/Button.tsx` line 59 sets `outline: 'none'` in the inline `style` object. Inline styles have higher specificity than any stylesheet rule, including the `.pathly-btn:focus-visible { outline: 2px solid #89b4fa }` rule in `index.html`. The focus ring never renders for keyboard users. The `className="pathly-btn"` was added, but the inline override neutralises it entirely.

### V2 — IconButton.tsx:36 — focus-visible contract — inline `outline: 'none'` overrides CSS `:focus-visible` rule

`studio/src/renderer/src/components/ui/IconButton.tsx` line 36 has the identical problem. `outline: 'none'` in `baseStyle` defeats `.pathly-btn:focus-visible`.

### V3 — Sidebar.module.css:56 — focus-visible contract — `.filterInput` suppresses outline with no `:focus-visible` recovery

`.filterInput` sets `outline: none` at line 56 and only restores `border-color` on `:focus` (not `:focus-visible`). There is no `.filterInput:focus-visible` rule. The filter search input has no visible keyboard focus indicator.

### V4 — TopBar.module.css:51,64 — focus-visible contract — `.topicSelect` and `.topicSelectArchive` suppress outline with no `:focus-visible` recovery

`.topicSelect` (line 51) and `.topicSelectArchive` (line 64) both set `outline: none` and use only `:focus` for border-color changes. Neither has a `:focus-visible` rule. The topic `<select>` elements have no keyboard focus ring.

---

## Warnings (non-blocking)

- `studio/src/renderer/src/components/FlowWizard.tsx` — multiple `outline: 'none'` inline styles (lines 98, 111, 131, 172, 187, 210, 250) — FlowWizard was not in scope for this fix pass but shares the same accessibility violation pattern.
- `studio/src/renderer/src/components/Editor/ConfigForm.module.css:64` — `outline: none` with no `:focus-visible` recovery — out of scope for this pass.
- `studio/src/renderer/src/components/NewItemDialog.module.css:60` — `outline: none` with no `:focus-visible` recovery — out of scope for this pass.

---

## Pass

- `index.html` — `.pathly-btn:focus-visible` and `.pathly-input:focus-visible` rules are present and correctly formed.
- `Input.tsx` — `className="pathly-input"` present; inline style does NOT contain `outline: 'none'`; JS `onFocus`/`onBlur` drives border-color only, not outline suppression. RESOLVED.
- `Sidebar.module.css` — all interactive button classes (`.expandBtn`, `.sectionHeader`, `.subdirHeader`, `.convRow`, `.itemRow`, `.bottomRow`, `.collapseBtn`, `.newBtn`) have `:focus-visible` rules.
- `TopBar.module.css` — `.backBtn`, `.terminalBtn`, `.publishBtn`, `.logClose` all have `:focus-visible` rules.
- S10: All 6 component files in `ui/` export from barrel (`index.ts`). All 7 ui/ files exist.
- S10: Zero ▶▼►▸ arrow characters found in tsx/ts source.
- S10: Sidebar chevrons are Lucide `ChevronRight`/`ChevronDown` icons — no text glyphs.
- S10: `ContextMenu` closes on outside `mousedown` and `Escape` key via `useEffect` document listeners.
