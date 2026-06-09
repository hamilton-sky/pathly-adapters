# User Stories — Editor & Notebook Enhancements

## Clarification resolved (PO question)
**"Ask Agent" scope:** The adapter picker IS the multi-adapter initiative landing in the Editor — it routes real prompts to Claude, Codex, and Antigravity/agy terminals, not just a thin clone of Explain. This is not deferred.

---

## Group A — Selection Tooltip (Preview mode)

### A1 — Copy selection
**As a** developer reviewing a skill file in Preview mode,
**I want** to copy my text selection to clipboard with one click,
**so that** I can paste it elsewhere without leaving the editor.

**Acceptance criteria:**
- A "Copy" icon button appears in the selection tooltip
- Clicking it calls `navigator.clipboard.writeText(selectedText)` and dismisses the tooltip
- No terminal is opened, no modal appears
- Works on any text type (plain text, inline code, link text)

---

### A2 — Find all occurrences
**As a** developer reading a skill file,
**I want** to select a term and highlight every occurrence in the preview,
**so that** I can quickly spot all uses of a pattern without switching to edit mode.

**Acceptance criteria:**
- A "Find" icon button appears in the selection tooltip
- Clicking it highlights all exact occurrences with a yellow `.findMark` tint
- Comment marks and find marks are independent (different `data-*` attributes)
- Find marks are cleared on the next `mousedown` anywhere in the preview
- Clicking "Find" again on a new selection replaces previous find marks

---

### A3 — Explain selection
**As a** developer confused by a piece of skill syntax or jargon,
**I want** to select the text and ask Claude to explain it,
**so that** I understand it in context without leaving Studio.

**Acceptance criteria:**
- An "Explain" icon button appears in the selection tooltip
- Clicking it opens a new terminal tab with Claude, passing: `Explain the following in the context of this file ({filename}):\n\n{selectedText}`
- The tab label reads "Explain · {first 30 chars}"
- No modal — goes straight to terminal
- Works when a file is loaded; button is not rendered if no `effectivePath`

---

### A4 — Ask any adapter (multi-adapter routing)
**As a** developer who uses Claude, Codex, and Antigravity in the same workflow,
**I want** to send a selected text passage to my choice of adapter,
**so that** I can compare answers or use the right tool for the job.

**Acceptance criteria:**
- An "Ask agent ▾" label+icon button appears in the selection tooltip
- Clicking it morphs the tooltip into: `[ ← ]  [ Claude ]  [ Codex ]  [ Antigravity ]`
- Clicking "← " returns to the main tooltip state
- Clicking an adapter:
  - Opens a new terminal tab labelled "{adapter} · {first 25 chars}"
  - Spawns the adapter's headless CLI with the selected text as context prompt:
    - Claude: `['claude', '-p', prompt, '--print', '--dangerously-skip-permissions']`
    - Codex: `['codex', 'exec', prompt, '--full-auto']`
    - Agy: `['agy', prompt]`
- Works when a file is loaded; not available if `effectivePath` is null

---

## Group B — MarkdownEditor enhancements (Edit / Split mode)

### B1 — Markdown formatting shortcuts
**As a** developer editing a skill file in the raw CodeMirror editor,
**I want** Ctrl+B / Ctrl+I / Ctrl+` to wrap my selection in bold / italic / code,
**so that** I can format text without typing the markdown syntax manually.

**Acceptance criteria:**
- Ctrl+B: wraps selection in `**…**`
- Ctrl+I: wraps selection in `_…_`
- Ctrl+`  wraps selection in backticks
- If no selection is active, the shortcut does nothing (no cursor-position insertion)
- These shortcuts take precedence over CodeMirror's built-in keymap (`Prec.high`)

---

### B2 — Template variable autocomplete
**As a** developer writing skill prompt templates with `<VARIABLE_NAME>` placeholders,
**I want** the editor to suggest variable names I've already used in the document,
**so that** I don't mistype them.

**Acceptance criteria:**
- When the user types `<` followed by one or more uppercase letters, autocomplete triggers
- Options are scanned from the current document (`/<([A-Z][A-Z0-9_]*)>/g`)
- Selecting a suggestion inserts the full `<VARIABLE_NAME>` token
- Uses `markdownLanguage.data.of({ autocomplete: source })` so it does NOT replace markdown's own completions
- Does not trigger on lowercase or non-letter characters after `<`

---

### B3 — Word and token count status bar
**As a** developer writing a skill prompt mindful of context window size,
**I want** to see a live word count and estimated token count while editing,
**so that** I can gauge prompt length without leaving Studio.

**Acceptance criteria:**
- A 22px status bar appears between the toolbar and the CodeMirror editor in Edit and Split modes
- Shows: `{N} words · ≈ {N} tokens` (token estimate: `Math.ceil(body.length / 4)`)
- Uses monospace font at 10px, `var(--text-muted)` color
- Updates live as the document changes (derived from `body` state)
- Not shown in Preview mode (no editor is visible)

---

### B4 — Fullscreen / focus mode
**As a** developer editing a long skill file in Studio,
**I want** to expand the editor to fill the entire window,
**so that** I can write without the sidebar and panel chrome competing for attention.

**Acceptance criteria:**
- A `Maximize2` icon button in the toolbar actions row (rightmost before Save) toggles fullscreen
- In fullscreen: the editor panel overlays `position: fixed; inset: 0; z-index: 900`
- Fullscreen state lives in `uiStore` (not local state) so it survives file navigation
- A floating exit badge (top-right, `opacity: 0.35` at rest, full on hover) shows `Esc to exit`
- Pressing Escape exits fullscreen
- Enter animation: scale 0.985 → 1 with opacity fade, 180ms
- Respects `prefers-reduced-motion`

---

## Group C — Notebook improvements

### C1 — Body cell collapse
**As a** developer reviewing a notebook with many body cells,
**I want** to collapse cells to just their heading,
**so that** I can see the overall structure without scrolling through all content.

**Acceptance criteria:**
- A `ChevronDown` / `ChevronUp` button is the leftmost item in the cell's strip control bar
- Clicking collapses/expands the cell body and heading input
- Collapsed cells show `opacity: 0.72` and a one-line title summary
- Collapsed state is **local** (not in undo history, not in skillNotebookStore)
- Collapse button is only available in `view` mode (not when `isEditing`)
- The strip and the type badge remain visible in all states

---

### C2 — Fragment cell hover preview
**As a** developer composing a notebook,
**I want** to hover a fragment chip to see what it contains,
**so that** I can make confident decisions about which fragments to insert without opening each one.

**Acceptance criteria:**
- After a 300ms hover delay, a popover appears below the fragment chip
- Popover shows: category badge + description text
- Popover is `pointer-events: none` (does not steal hover state)
- Popover is `position: fixed` (not clipped by overflow:hidden parents)
- Popover position is set via `ref.current.style.setProperty` in a `useEffect`
- Popover does NOT appear when the cell's context menu is open
- `z-index: 150` (below cell menus at 200, above canvas content)
- Closes immediately when pointer leaves the chip

---

### C3 — Cell keyboard shortcuts
**As a** developer keyboard-navigating the notebook,
**I want** Alt+Enter / Alt+↑ / Alt+↓ to add and reorder cells,
**so that** I can build notebooks without touching the mouse.

**Acceptance criteria:**
- `Alt+Enter`: inserts a new body cell below the currently focused cell
- `Alt+↑`: moves the focused cell one position up
- `Alt+↓`: moves the focused cell one position down
- Focused cell is tracked in `NotebookCanvas` local state (`focusedCellId`) via `onFocusCapture`
- All three shortcuts are combined with the existing Ctrl+Z/Redo handler into one `keydown` effect
- In edit mode (textarea focused), `Alt+Enter` does nothing (does not compete with "new line")
- A transient HUD hint strip appears at the bottom of the canvas when a cell is first focused, fades after 2400ms

---

## Priority order (MVP → nice-to-have)

| Priority | Feature | Rationale |
|---|---|---|
| P1 — MVP | A1 Copy, A3 Explain, B1 Formatting shortcuts, B3 Status bar, C1 Cell collapse | High value, low risk |
| P2 — Core | A4 Ask agent, B4 Fullscreen, C2 Fragment hover | Core UX, moderate complexity |
| P3 — Polish | A2 Find, B2 Autocomplete, C3 Keyboard shortcuts + HUD | Power-user, higher complexity |
