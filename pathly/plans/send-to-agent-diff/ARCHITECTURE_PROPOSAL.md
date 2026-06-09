# Architecture Proposal — send-to-agent-diff

## Design decisions

### No new IPC channels needed
`window.pathly.fs` already has `read`, `write`, and `delete`. The confirm flow is:
1. `write(originalPath, newContent)` — atomic via internal `.tmp` rename in `fs:write`
2. `delete(draftPath)` — removes the `.draft`

Adding a dedicated `rename` IPC would be cleaner in theory but adds main/preload/type surface for no functional benefit — `write` + `delete` is equivalent and already safe.

### Section-level granularity, not line-level unified diff
Line-level diff (unified diff format) is powerful but complex to selectively apply to markdown. Applying a subset of line-level hunks can produce malformed markdown if section boundaries are split.

Section-level diff (split on `## ` headings) is naturally coherent: each hunk is a complete section that can be independently replaced. For Pathly skill files, sections are the right granularity — they represent distinct rules or behaviors. A user who wants to accept "the new Review mindset section" but keep "the old Output format section" can do so cleanly.

Limitation: preamble content (before the first `## `) is treated as a single hunk. This is fine for skill files which always start with a brief description.

### Terminal exit detection via existing `terminal.onExit`
`window.pathly.terminal.onExit` is already in the preload and typed in `global.d.ts`. It broadcasts all tab exits. We match by `tabId` and unsubscribe immediately after the first match — no memory leak.

Alternative considered: SSE event from FSM server. Rejected — "Send to Agent" is not a pipeline run, it doesn't register a runner, so the FSM server doesn't track it.

### Unified toggle chip for all hunk types (not radio + checkbox)
Three different control patterns (radio for changed, checkbox for added, checkbox for removed) create cognitive mode-switching cost. All three types use one control pattern: a single toggle chip button per card. The chip label changes by type ("Keep original" / "Use draft", "Exclude" / "Include", "Discard" / "Keep"). This gives identical visual language for all hunks regardless of status.

### Collapsed-by-default hunk cards
Cards show heading + type badge + one preview line collapsed. Expanded on click to reveal old+new text blocks. Sets `reviewed = true` on first expand. An "unreviewed" warning in the footer prevents accidental apply-all. This mirrors the `SkillSplitModal` cellPreview pattern — no new design primitive needed.

### Three-button footer: Discard / Close / Apply
`Close` is a non-destructive dismiss (keeps draft on disk, re-surfaces on next file open). `Discard agent changes` is destructive with an inline confirmation row (not `window.confirm()`). This distinction is critical: users must be able to exit the overlay temporarily without destroying the draft. `Reject` (the original name) was too ambiguous — it collided with "rejecting comments" semantics.

### DiffViewer as an overlay (not a new tab/route)
The viewer is conceptually tied to the file currently open in the editor. A modal overlay keeps that relationship clear. It also blocks accidental edits to the file while the draft review is pending, which is the right constraint.

### CommentsPanel owns the spawn, Editor owns the draft state
Responsibility split:
- CommentsPanel: knows about comments, builds the prompt, triggers the spawn, registers exit listener
- Editor: owns `draftPath` state, renders the overlay, handles confirm/reject

This keeps CommentsPanel focused on comment UX and Editor focused on file state. The `onDraftReady` prop is the clean boundary between them.

### Default accepted = true for changed/added, false for removed
Users are more likely to want to keep Claude's additions than to discard them. Defaulting to "accept all" means a single "Apply N changes" click applies everything — the reviewer only needs to intervene for sections they want to revert. This mirrors standard code review defaults (accept all, selectively request changes).
