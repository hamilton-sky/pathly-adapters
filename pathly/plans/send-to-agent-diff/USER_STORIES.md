# User Stories — send-to-agent-diff

## US-1: Draft instead of overwrite

**As a** user with comments on a skill file,
**I want** "Send to Agent" to write a `.draft` instead of overwriting the original,
**so that** I can review what changed before committing to it.

### Acceptance criteria
- Clicking "Send to Agent" spawns Claude with a prompt that writes `<filepath>.draft` not `<filepath>`
- The original file is unchanged while the agent runs
- When the terminal exits, the Studio checks for the `.draft` and surfaces the diff viewer if it exists

---

## US-2: Section-level diff viewer

**As a** user reviewing a draft,
**I want** to see a section-by-section comparison of old vs new,
**so that** I understand exactly what the agent changed.

### Acceptance criteria
- Viewer shows every section (## heading + content) that changed, was added, or was removed
- Unchanged sections are not shown (they are always included in the output)
- Content before the first `## ` heading is treated as one implicit preamble section and diffed like any other
- Each changed section shows old text and new text in a collapsed card (expandable)
- Each section has a single toggle chip — one control pattern for all three hunk types
- Type badge (ADDED / REMOVED / CHANGED) + colored left border on every hunk card
- If the draft is identical to the original (zero changes), the viewer does not appear; a toast notification is shown instead

---

## US-3: Selective acceptance

**As a** user in the diff viewer,
**I want** to toggle individual sections independently,
**so that** I can accept some changes and reject others.

### Acceptance criteria
- Toggling one hunk does not affect other hunks
- A live preview panel shows the file as it will look after applying current selections
- The preview updates immediately when any toggle changes

---

## US-4: Apply, close, or discard draft

**As a** user who has made selections in the diff viewer,
**I want** three clear exit paths — apply my selections, close temporarily, or permanently discard the draft —
**so that** I can review at my own pace and the original is never left in a broken state.

### Acceptance criteria
- **Apply** ("Apply N of M changes"): reconstructs file content from selections, writes to original path via `fs:write` (atomic `.tmp` rename internally), deletes `.draft`, closes viewer, editor reloads
- **Close** (ghost button): closes the overlay but keeps `.draft` on disk; re-opening the same file re-renders the viewer from the existing draft
- **Discard agent changes** (destructive, far-left): shows an inline confirmation row ("This permanently deletes the draft — are you sure?") before deleting `.draft`; uses `var(--red)` styling; does not use `window.confirm()`
- CTA shows exact counts: "Apply 2 of 3 changes" — N = accepted non-unchanged hunks, M = total non-unchanged hunks
- If `.draft` disappears unexpectedly while viewer is open, viewer closes gracefully with an error message
- A "You have N unreviewed sections" warning appears in the footer when some hunk cards have never been expanded
