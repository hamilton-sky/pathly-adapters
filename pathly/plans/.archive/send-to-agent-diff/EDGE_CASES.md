# Edge Cases — send-to-agent-diff

## EC-1: Agent fails / exits without writing `.draft` [CRITICAL v1]
**Scenario:** Agent errors out or is killed before writing the draft file, OR writes a partial/empty draft due to a mid-run crash.
**Behavior:** `window.pathly.fs.read(filePath + '.draft')` returns `null` or empty string → `onDraftReady` is never called → no DiffViewer appears.
**Guard:** Check `content !== null && content.trim().length > 0` before calling `onDraftReady`. Empty draft = same as no draft.
**No change needed** to original file. Terminal tab shows the error.

## EC-1b: Original file edited by user while agent runs [CRITICAL v1]
**Scenario:** User manually edits and saves the file in the editor while Claude is writing the draft.
**Risk:** `handleDiffApply` calls `fs.write(effectivePath, reconstructedContent)` — this reconstructed content was built from the original snapshot taken at spawn time, not the current file state. The user's edits are silently overwritten.
**Mitigation:** In `handleDiffApply`, re-read the current file before writing. If it differs from what `useDraftDiff` loaded as `originalContent`, show a warning: "The file was modified since the draft was created. Applying will overwrite those changes." Let user confirm or cancel.

## EC-2: User closes the editor while agent is running
**Scenario:** File changes to a different item (`effectivePath` changes) before agent exits.
**Behavior:** `useEffect` cleanup clears `draftPath` state. When the exit listener fires, `filePath` in the closure refers to the old path. The draft will exist at `<oldPath>.draft`. The `onDraftReady` callback would fire but the Editor has already reset — `draftPath` will be set to the old path while the wrong file is open.
**Mitigation:** CommentsPanel should check `filePath` still matches `effectivePath` before calling `onDraftReady`. Pass the current `effectivePath` as a ref from Editor to CommentsPanel, or simply let the DiffViewer guard: `originalPath` mismatch with `effectivePath` → auto-reject and delete draft.

## EC-2b: Orphaned `.draft` from a prior crashed run [CRITICAL v1]
**Scenario:** User previously ran "Send to Agent" and the draft was never resolved (app crashed, user dismissed without acting). On next open of the same file, a stale `.draft` exists.
**Behavior:** Editor/index.tsx's `useEffect` on `effectivePath` change should also check for a pre-existing `.draft` and auto-set `draftPath` state if one is found. This surfaces the recovery UI immediately on file open.
**Implementation:** Add a `fs.read(effectivePath + '.draft')` check inside the `useEffect` that loads the file. If content is non-null and non-empty, call `setDraftPath(effectivePath + '.draft')`.

## EC-3: `.draft` file already exists from a previous failed run
**Scenario:** User clicked "Send to Agent" twice, or a previous run left a stale `.draft`.
**Behavior:** Second click overwrites the stale draft because Claude writes a new one. When the second exit fires, the new draft is shown.
**Note:** If user clicks "Send to Agent" while a DiffViewer is already open, we should guard against showing two viewers. `handleSendToAgent` should early-return if `draftPath` is already set.

## EC-4: File has no `## ` headings (no sections)
**Scenario:** A skill file with only preamble content and no `## ` headings.
**Behavior:** `parseIntoSections` returns the entire content as a single `__preamble__` section. The diff will show the whole-file change as one hunk (or unchanged if nothing changed). User gets a single "Keep original" / "Use draft" toggle for the entire file. This is acceptable behavior.

## EC-5: Agent rewrites entire file (all sections changed)
**Scenario:** Agent rewrites every section — large diff.
**Behavior:** All hunks show as `changed`, all default to `accepted = true`. User can deselect individual sections. The "Apply N changes" button shows the count of accepted non-unchanged hunks.

## EC-6: `window.pathly.fs.write` throws on confirm
**Scenario:** Disk full, permission error, or race condition.
**Behavior:** `handleDiffConfirm` should catch the error and surface it to the user (set `saveError` state). The DiffViewer should remain open so the user can retry or reject.

## EC-7: User clicks backdrop to close
**Scenario:** User clicks outside the modal.
**Behavior:** Backdrop click calls `onReject` → draft is deleted, viewer closes. This matches the "discard" intent of clicking outside a modal.

## EC-8: File path has spaces or special characters (Windows)
**Scenario:** Path like `C:\Users\Yafit\pathly-adapters\src\my skill\reviewer.md`
**Behavior:** `filePath + '.draft'` is `C:\...\my skill\reviewer.md.draft` — a valid path. `fs:read` and `fs:delete` handle it since they use Node `fs` directly, not shell. The agent prompt uses the normalized forward-slash path which Claude Code handles correctly on Windows.
