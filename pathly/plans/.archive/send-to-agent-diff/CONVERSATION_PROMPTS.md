# Conversation Prompts — send-to-agent-diff

---

## Conversation 1 — Draft-mode wiring

Read pathly/plans/send-to-agent-diff/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

You are implementing **Conversation 1** of the `send-to-agent-diff` feature. The goal is to redirect the "Send to Agent" flow so Claude writes a `.draft` file instead of overwriting the original, and wire the terminal exit event so the Editor knows a draft is ready.

### Phase 1 — commentUtils.ts
In `studio/src/renderer/src/components/Editor/commentUtils.ts`, change `buildSendPrompt`:
- The last content line currently says: `Write the complete revised content back to: ${norm}`
- Change it to: `Write the complete revised content to: ${norm}.draft`
- Do NOT change any other part of `buildSendPrompt` or `deriveLineNumber` or `getSpawnCwd`.

### Phase 2 — CommentsPanel.tsx
In `studio/src/renderer/src/components/Editor/CommentsPanel/CommentsPanel.tsx`:
- Add `onDraftReady: (draftPath: string) => void` to the Props interface
- Destructure it in the component props
- In `handleSendToAgent`, after `await window.pathly.terminal.spawn(...)`, add:
  ```ts
  const unsub = window.pathly.terminal.onExit((exitedTabId) => {
    if (exitedTabId !== tabId) return
    unsub()
    void window.pathly.fs.read(filePath + '.draft').then((content) => {
      if (content !== null) onDraftReady(filePath + '.draft')
    })
  })
  ```
- The `filePath` prop is already in scope. Use the raw `filePath` (not `norm`) for the `.draft` path — the original path is what the OS will see.

### Phase 3 — Editor/index.tsx
In `studio/src/renderer/src/components/Editor/index.tsx`:
- Add `const [draftPath, setDraftPath] = useState<string | null>(null)` near the other state declarations
- Inside the `useEffect` that resets state on `effectivePath` change (around line 129), add `setDraftPath(null)` at the start
- In the JSX, pass `onDraftReady={setDraftPath}` to the `<CommentsPanel ... />` element

### Verify
Run `npm run typecheck` from the repo root. Zero type errors is the done condition.
If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with git checkout on affected files and retry.

---

## Conversation 2 — DraftDiffViewer component

Read pathly/plans/send-to-agent-diff/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

You are implementing **Conversation 2** of the `send-to-agent-diff` feature. Create the `DraftDiffViewer` component that shows the user a section-level diff and lets them selectively accept or reject individual hunks.

Do NOT touch `commentUtils.ts`, `CommentsPanel.tsx`, or `Editor/index.tsx` yet — those are wired in other conversations.

Create the following files in `studio/src/renderer/src/components/Editor/DraftDiffViewer/`. Each file gets its own `.module.css` sibling. All buttons must have `type="button"`. No `style={{}}` props.

### Phase 4 — useDraftDiff.ts

```ts
import { useState, useEffect } from 'react'

export type HunkStatus = 'unchanged' | 'changed' | 'added' | 'removed'

export interface DiffHunk {
  id: string
  heading: string           // '__preamble__' for content before first ##
  originalContent: string | null
  draftContent: string | null
  status: HunkStatus
  accepted: boolean         // true = use draft version
  reviewed: boolean         // true after first card expand
}

function parseIntoSections(text: string): Array<{ heading: string; content: string }> {
  const parts = ('\n' + text).split(/\n(?=## )/)
  return parts
    .map((p) => p.trimStart())
    .filter(Boolean)
    .map((p) => {
      const nl = p.indexOf('\n')
      if (p.startsWith('## ') && nl !== -1) {
        return { heading: p.slice(3, nl).trim(), content: p.slice(nl + 1).trim() }
      }
      return { heading: '__preamble__', content: p.trim() }
    })
    .filter((s) => s.heading || s.content)
}

export function reconstruct(hunks: DiffHunk[]): string {
  return hunks
    .filter((h) => h.status !== 'removed' || h.accepted)
    .map((h) => {
      const content = h.status === 'added' || (h.status === 'changed' && h.accepted)
        ? h.draftContent ?? ''
        : h.originalContent ?? ''
      if (h.heading === '__preamble__') return content
      return `## ${h.heading}\n\n${content}`
    })
    .join('\n\n')
}

export function useDraftDiff(originalPath: string, draftPath: string) {
  const [hunks, setHunks] = useState<DiffHunk[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    setLoading(true)
    setError(false)
    Promise.all([
      window.pathly.fs.read(originalPath),
      window.pathly.fs.read(draftPath),
    ]).then(([orig, draft]) => {
      const origSections = parseIntoSections(orig ?? '')
      const draftSections = parseIntoSections(draft ?? '')
      const origMap = new Map(origSections.map((s) => [s.heading, s.content]))
      const draftMap = new Map(draftSections.map((s) => [s.heading, s.content]))
      const allHeadings = [
        ...new Set([...origSections.map((s) => s.heading), ...draftSections.map((s) => s.heading)])
      ]
      const result: DiffHunk[] = allHeadings.map((heading, i) => {
        const orig_ = origMap.get(heading) ?? null
        const draft_ = draftMap.get(heading) ?? null
        let status: HunkStatus = 'unchanged'
        let accepted = false
        if (orig_ === null) { status = 'added'; accepted = true }
        else if (draft_ === null) { status = 'removed'; accepted = false }
        else if (orig_ !== draft_) { status = 'changed'; accepted = true }
        return { id: String(i), heading, originalContent: orig_, draftContent: draft_, status, accepted, reviewed: false }
      })
      setHunks(result)
      setLoading(false)
    }).catch(() => { setError(true); setLoading(false) })
  }, [originalPath, draftPath])

  function toggle(id: string): void {
    setHunks((prev) => prev.map((h) => h.id === id ? { ...h, accepted: !h.accepted } : h))
  }
  function markReviewed(id: string): void {
    setHunks((prev) => prev.map((h) => h.id === id ? { ...h, reviewed: true } : h))
  }

  const nonUnchanged = hunks.filter((h) => h.status !== 'unchanged')
  const acceptedCount = nonUnchanged.filter((h) => h.accepted).length
  const totalChanged = nonUnchanged.length
  const unreviewedCount = nonUnchanged.filter((h) => !h.reviewed).length

  return { hunks, loading, error, toggle, markReviewed, acceptedCount, totalChanged, unreviewedCount, reconstruct: () => reconstruct(hunks) }
}
```

### Phase 5 — DraftHunkCard.tsx + DraftHunkCard.module.css

Props: `{ hunk: DiffHunk; onToggle: (id: string) => void; onMarkReviewed: (id: string) => void }`

- Collapsed by default (use local `expanded` state)
- Click on card body → toggle `expanded`, call `onMarkReviewed(hunk.id)` on first expand
- Type badge: "ADDED" / "REMOVED" / "CHANGED" with colored background (color-mix pattern, see SkillSplitModal typeBadge)
- Left border color: `var(--green)` for added, `var(--red)` for removed, `var(--accent)` for changed
- Collapsed: heading + badge + first non-empty line of draft/original as preview (truncated)
- Expanded: shows two labeled text blocks (`ORIGINAL` / `DRAFT`) side by side or stacked; for `removed`, only ORIGINAL block; for `added`, only DRAFT block
- Toggle chip: single `<button>` per card, label changes by type+accepted state:
  - changed + accepted=true: "Using draft" → click → accepted=false, label "Using original"
  - changed + accepted=false: "Using original" → click → accepted=true, label "Using draft"
  - added + accepted=true: "Including" → click → "Excluded"
  - added + accepted=false: "Excluded" → click → "Including"
  - removed + accepted=false: "Discarding" → click → "Keeping"
  - removed + accepted=true: "Keeping" → click → "Discarding"

### Phase 5b — DraftHunkList.tsx + DraftHunkList.module.css

Props: `{ hunks: DiffHunk[]; onToggle: (id: string) => void; onMarkReviewed: (id: string) => void }`

- Panel header: "CHANGES" badge with count of non-unchanged hunks
- Scrollable list of `<DraftHunkCard>` for non-unchanged hunks only
- Unchanged hunks: not shown (silently included in output)

### Phase 6 — DraftPreviewPanel.tsx + DraftPreviewPanel.module.css

Props: `{ content: string; changedHunks: DiffHunk[] }`

- Header with two toggle buttons: "Result" | "Changes"
- "Result" mode: `<MarkdownRenderer content={content} />` (import from `../../shared/MarkdownRenderer/MarkdownRenderer`)
- "Changes" mode: list of only accepted non-unchanged hunks — heading + draft text block (no MarkdownRenderer needed)
- Default: "Result" mode

### Phase 6b — DraftDiffFooter.tsx + DraftDiffFooter.module.css

Props: `{ unreviewedCount: number; acceptedCount: number; totalChanged: number; onDiscard: () => void; onClose: () => void; onApply: () => void }`

- Far left: "Discard agent changes" — `var(--red)` border/text; on click toggles `showConfirm` local state
  - When `showConfirm=true`: inline row replaces/overlays footer — "Permanently delete draft?" + "Yes, discard" + "Cancel"
  - "Yes, discard" calls `onDiscard`; "Cancel" resets `showConfirm=false`
- Middle: "Close" — ghost `btnCancel` style — calls `onClose` (keeps draft on disk)
- Far right: "Apply N of M changes" — primary, disabled when `acceptedCount === 0`
  - Label: `Apply ${acceptedCount} of ${totalChanged} changes`
  - On click calls `onApply`
- Warning row above buttons (only when `unreviewedCount > 0`): `${unreviewedCount} sections not yet reviewed` — `var(--text-muted)`, small font

### Phase 6c — DraftDiffViewer.tsx + DraftDiffViewer.module.css

This is the modal shell only — no business logic.

Props: `{ originalPath: string; draftPath: string; onApply: (newContent: string) => void; onClose: () => void; onDiscard: () => void }`

- Use `useDraftDiff(originalPath, draftPath)`
- Backdrop: full-screen fixed, click calls `onClose` (not discard)
- Modal: click stops propagation; centered, max-width 800px, max-height 80vh
- Header: "Reviewing draft — {filename from draftPath}"
- Loading state: "Loading diff…" centered
- Error state: "Could not load draft" + Retry button (re-mounts hook) + Dismiss button (calls `onClose`)
- Empty state (no non-unchanged hunks after load): "No changes detected — draft is identical" + single Close button (calls `onClose`) — do NOT call `onDiscard` here
- Normal state: body = `<DraftHunkList>` | divider | `<DraftPreviewPanel>` + footer = `<DraftDiffFooter>`
- `onApply` in footer → calls `onApply(reconstruct())`

### Verify
Run `npm run typecheck` from the repo root. Zero type errors.
If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with git checkout on affected files and retry.

---

## Conversation 3 — Mount overlay + confirm/reject handlers

Read pathly/plans/send-to-agent-diff/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

You are implementing **Conversation 3** of the `send-to-agent-diff` feature. Conversations 1 and 2 must be done first. Mount the `DraftDiffViewer` in `Editor/index.tsx` and wire the apply, close, and discard handlers.

### Phase 7 — Import and mount DraftDiffViewer
In `studio/src/renderer/src/components/Editor/index.tsx`:
- Add import: `import { DraftDiffViewer } from './DraftDiffViewer/DraftDiffViewer'`
- At the bottom of the JSX return, after the `CommentModal` block, add:
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
- Note: `onClose` sets `draftPath(null)` but does NOT delete the file — draft stays on disk

### Phase 7b — Check for orphaned draft on file open
Still in `Editor/index.tsx`, inside the `useEffect` that fires on `effectivePath` change (the one that calls `readFile`, around line 129):
- After the `setLoading(true)` line, add a check for an existing draft:
  ```ts
  window.pathly.fs.read(effectivePath + '.draft').then((draftContent) => {
    if (draftContent && draftContent.trim().length > 0) setDraftPath(effectivePath + '.draft')
  }).catch(() => {})
  ```
- This surfaces the DiffViewer when a stale draft exists from a previous run

### Phase 8 — handleDiffApply
Add this async function inside the Editor component (near `performSave`):
```ts
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

### Phase 9 — handleDiffDiscard
Add this async function inside the Editor component:
```ts
async function handleDiffDiscard(): Promise<void> {
  if (!effectivePath) return
  await window.pathly.fs.delete(effectivePath + '.draft')
  setDraftPath(null)
}
```

### Verify
1. Run `npm run typecheck` from the repo root — zero errors.
2. Manual golden path: open Studio → open a skill file → add a comment → click "Send to Agent" → wait for terminal to finish → diff viewer appears → expand a card → toggle a hunk → "Apply N of M changes" → editor shows updated content → `.draft` file is gone.
3. Manual close path: open diff viewer → click "Close" → viewer closes → `.draft` still exists on disk → reopen the same file → viewer re-appears automatically.
4. Manual discard path: open diff viewer → click "Discard agent changes" → inline confirm → "Yes, discard" → editor unchanged → `.draft` file is gone.
5. Manual orphan path: manually create a `.draft` file alongside an open skill file → close and reopen the file in Studio → diff viewer appears automatically.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with git checkout on affected files and retry.
