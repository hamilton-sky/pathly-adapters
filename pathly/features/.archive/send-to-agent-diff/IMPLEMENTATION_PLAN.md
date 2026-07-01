# Implementation Plan — send-to-agent-diff

---

## Conversation 1 — Draft-mode wiring   ← Conversation: 1

### Phase 1 — Redirect agent output to `.draft`
File: `studio/src/renderer/src/components/Editor/commentUtils.ts`
Done when: `buildSendPrompt()` tells Claude to write to `<filepath>.draft` not `<filepath>`
Purpose: Prevents agent from overwriting the original file
Depends on: nothing
Enables: Phase 2 (knowing where the draft will land)
Verify: Open Studio, add a comment, click "Send to Agent", confirm terminal command includes `.draft` in the write instruction

Change:
- In the last line of the prompt array, replace `Write the complete revised content back to: ${norm}` with `Write the complete revised content to: ${norm}.draft`

### Phase 2 — CommentsPanel: notify Editor when draft exists
File: `studio/src/renderer/src/components/Editor/CommentsPanel/CommentsPanel.tsx`
Done when: CommentsPanel accepts `onDraftReady: (draftPath: string) => void` prop and calls it when the agent terminal exits and `<filepath>.draft` exists
Purpose: Bridges the terminal lifecycle event to the Editor state
Depends on: Phase 1 (draft path is now deterministic)
Enables: Editor can show DiffViewer when draft is ready
Verify: Console.log in `onDraftReady` fires after agent exits

Changes:
- Add `onDraftReady: (draftPath: string) => void` to Props interface
- In `handleSendToAgent`, after `await window.pathly.terminal.spawn(...)`, register a one-time `terminal.onExit` listener:
  ```
  const unsub = window.pathly.terminal.onExit((exitedTabId) => {
    if (exitedTabId !== tabId) return
    unsub()
    void window.pathly.fs.read(filePath + '.draft').then((content) => {
      if (content !== null) onDraftReady(filePath + '.draft')
    })
  })
  ```
- Clean up: unsub is called inside the handler on first match, so no leak

### Phase 3 — Editor: add draftPath state + pass prop
File: `studio/src/renderer/src/components/Editor/index.tsx`
Done when: Editor has `draftPath` state, clears it on file change, and passes `onDraftReady` to CommentsPanel
Purpose: Holds the trigger for showing the DiffViewer
Depends on: Phase 2
Enables: Conversation 3 (mounting DiffViewer)
Verify: State is set after agent run (verifiable in React DevTools)

Changes:
- Add `const [draftPath, setDraftPath] = useState<string | null>(null)` near other state
- Reset on file change: add `setDraftPath(null)` inside the `useEffect` that depends on `effectivePath`
- Pass `onDraftReady={setDraftPath}` to `<CommentsPanel ... />`

---

## Conversation 2 — DraftDiffViewer component   ← Conversation: 2

### Phase 4 — useDraftDiff hook
File: `studio/src/renderer/src/components/Editor/DraftDiffViewer/useDraftDiff.ts`
Done when: Hook reads original + draft, returns `DiffHunk[]` with per-hunk `accepted` + `reviewed` flags, a `toggle(id)` dispatcher, and a `reconstruct()` function
Purpose: All diff logic isolated — components are purely presentational
Depends on: `window.pathly.fs.read` (already in global.d.ts)
Enables: Phases 5–6 (components stay thin)
Verify: `npm run typecheck` passes

Types:
```
type HunkStatus = 'unchanged' | 'changed' | 'added' | 'removed'
interface DiffHunk {
  id: string
  heading: string          // '__preamble__' for content before first ## 
  originalContent: string | null
  draftContent: string | null
  status: HunkStatus
  accepted: boolean        // true = use draft version
  reviewed: boolean        // set to true on first card expand
}
```

Logic:
- `parseIntoSections` — first, check for content before the first `## ` and emit as `{heading: '__preamble__', content}`. Then split on `\n## ` boundaries.
- Align sections by heading; produce `DiffHunk[]`
- `unchanged`: identical → always included, accepted irrelevant
- `changed`: different content → default `accepted = true`, `reviewed = false`
- `added`: draft-only → default `accepted = true`, `reviewed = false`
- `removed`: original-only → default `accepted = false`, `reviewed = false`
- `reconstruct(hunks)`: reassemble text from accepted choices
- `unreviewedCount`: count of non-unchanged hunks where `reviewed === false`

### Phase 5 — DraftHunkCard + DraftHunkList
Files:
- `DraftHunkCard.tsx` — single hunk card (type badge, toggle chip, collapsed/expanded text blocks)
- `DraftHunkList.tsx` — left panel (section count header, scrollable list of cards)
- `DraftHunkCard.module.css` + `DraftHunkList.module.css`

Done when: Hunk cards render collapsed by default; expand on click; toggle chip updates accepted state; type badges are color-coded
Purpose: Keeps each sub-component under 150 lines; DraftHunkCard is the densest unit
Depends on: Phase 4 (hook shape)
Enables: Phase 6 (modal shell can import these)
Verify: `npm run typecheck` passes

DraftHunkCard details (per design review):
- All three hunk types use the same control: a single toggle chip button ("Keep original" ↔ "Use draft" for changed; "Exclude" ↔ "Include" for added; "Discard" ↔ "Keep" for removed)
- Collapsed state: heading + type badge + one-line preview of draft text + toggle chip (52px height target)
- Expanded state: click anywhere on card body to expand; shows old text block above new text block with a `ORIGINAL` / `DRAFT` label; sets `reviewed = true` on first expand
- Type badge + left border color: `added` = `var(--green)`, `removed` = `var(--red)`, `changed` = `var(--accent)`

### Phase 6 — DraftPreviewPanel + DraftDiffFooter + DraftDiffViewer shell
Files:
- `DraftPreviewPanel.tsx` + `DraftPreviewPanel.module.css` — right panel with "Result" / "Changes" toggle
- `DraftDiffFooter.tsx` + `DraftDiffFooter.module.css` — three-button footer with inline discard confirm
- `DraftDiffViewer.tsx` + `DraftDiffViewer.module.css` — modal shell (backdrop, header, body layout)

Done when: Full overlay renders; footer shows three buttons; preview switches between full result and changes-only view; no `style={{}}` props
Purpose: Modal shell stays under 60 lines by delegating to sub-components
Depends on: Phase 5
Enables: Conversation 3 (mounting)
Verify: `npm run typecheck` passes

DraftPreviewPanel: header with "Result" | "Changes" toggle buttons. "Result" = MarkdownRenderer of `reconstruct(hunks)`. "Changes" = list of only the accepted non-unchanged hunks (heading + draft text), no full MarkdownRenderer needed.

DraftDiffFooter props: `{ unreviewedCount, acceptedCount, totalChanged, onDiscard, onClose, onApply }`
- Far left: "Discard agent changes" — `var(--red)` border, on click shows inline confirmation row ("Permanently delete draft? Yes / Cancel") for 1 line; no `window.confirm()`
- Middle: "Close" — ghost button, calls `onClose` (keeps draft on disk)
- Far right: "Apply N of M changes" — disabled when `acceptedCount === 0`; `N` = acceptedCount, `M` = totalChanged
- Warning row above buttons (when `unreviewedCount > 0`): "N sections not yet reviewed" in `var(--text-muted)` — does not block Apply

DraftDiffViewer shell props: `{ originalPath, draftPath, onApply(content), onClose, onDiscard }`
- Backdrop: full-screen, click calls `onClose` (not discard — matches "Close" semantics)
- Modal: centered, max-width 800px, max-height 80vh, flex column
- Header: "Reviewing draft — {filename}"
- Empty state: when `hunks.length === 0` (after load) show "No changes detected" + single "Close" button
- Error state: when read fails show "Could not load draft" + Retry + Dismiss

---

## Conversation 3 — Mount overlay + confirm/reject handlers   ← Conversation: 3

### Phase 7 — Mount DraftDiffViewer in Editor
File: `studio/src/renderer/src/components/Editor/index.tsx`
Done when: DraftDiffViewer renders as overlay when `draftPath !== null`
Purpose: Connects the state from Conversation 1 to the component from Conversation 2
Depends on: Conv 1 (draftPath state), Conv 2 (DraftDiffViewer component)
Enables: Phase 8
Verify: After agent run, overlay appears; without a draft file, nothing shows

Changes:
- Import `DraftDiffViewer`
- At bottom of JSX (after CommentModal):
  ```tsx
  {draftPath && effectivePath && (
    <DraftDiffViewer
      originalPath={effectivePath}
      draftPath={draftPath}
      onApply={(content) => void handleDiffApply(content)}
      onClose={() => setDraftPath(null)}
      onDiscard={() => void handleDiffDiscard()}
    />
  )}
  ```
- Note: `onClose` sets `draftPath` to null but does NOT delete the draft — the draft stays on disk for later review

### Phase 8 — Apply handler: write + reload
File: `studio/src/renderer/src/components/Editor/index.tsx`
Done when: Apply writes reconstructed content to original, deletes draft, reloads editor body
Purpose: Atomic apply — user sees updated content immediately without manual reload
Depends on: Phase 7
Enables: US-4 apply path
Verify: After apply, editor shows new content; `.draft` file no longer exists

```
async function handleDiffApply(newContent: string): Promise<void> {
  if (!effectivePath) return
  await window.pathly.fs.write(effectivePath, newContent)
  await window.pathly.fs.delete(effectivePath + '.draft')
  setDraftPath(null)
  const parsed = parseFrontmatter(newContent)
  setConfig(parsed.config)
  setBody(parsed.body)
  clearDirty(effectivePath)
}
```

### Phase 9 — Discard handler: delete draft
File: `studio/src/renderer/src/components/Editor/index.tsx`
Done when: Discard deletes the draft and closes the viewer; original untouched
Purpose: Clean discard path (triggered from footer inline confirm, not directly from backdrop click)
Depends on: Phase 7
Enables: US-4 discard path
Verify: After discard, editor shows original content; `.draft` file no longer exists

```
async function handleDiffDiscard(): Promise<void> {
  if (!effectivePath) return
  await window.pathly.fs.delete(effectivePath + '.draft')
  setDraftPath(null)
}
```
