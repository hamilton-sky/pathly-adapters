# REVIEW_FAILURES — send-to-agent-diff Conv 1

## Violations

### V1 — CommentsPanel.tsx:54-68 — Logic correctness — resolvedTabId null-window

**File:** `studio/src/renderer/src/components/Editor/CommentsPanel/CommentsPanel.tsx`
**Lines:** 54, 57-58, 68

`tabId` is computed at line 50 before the listener is registered. The `resolvedTabId`
variable is declared `null` at line 54, but only assigned `tabId` at line 68 (after
`await terminal.spawn` resolves). The listener guard at line 58 reads:

```ts
if (resolvedTabId === null || exitedTabId !== resolvedTabId) return
```

If the terminal exits during the IPC roundtrip of `spawn` (between line 65 and line 68),
`resolvedTabId` is still `null` and the exit event is silently dropped. The handler
never fires and `onDraftReady` is never called.

`tabId` is already in closure scope and is the correct value. The fix is to remove
`resolvedTabId` entirely and use `tabId` directly in the guard.

**Required fix:**
- Delete `let resolvedTabId: string | null = null` (line 54)
- Change the listener guard from `resolvedTabId === null || exitedTabId !== resolvedTabId`
  to `exitedTabId !== tabId`
- Delete `resolvedTabId = tabId` (line 68)

---

### V2 — CommentsPanel.tsx:70-76 — Logic correctness / stale-data — early-exit check fires on stale draft

**File:** `studio/src/renderer/src/components/Editor/CommentsPanel/CommentsPanel.tsx`
**Lines:** 70-76

After `spawn` resolves, the code reads `norm + '.draft'` immediately and calls
`onDraftReady` if content exists. A `.draft` file from a prior unresolved run satisfies
this check. When it does:

1. The new exit listener is unsubscribed (`exitUnsubRef.current?.()`, line 73).
2. `onDraftReady` fires with the path of the **old** draft (line 75).
3. The new Claude Code run completes later, its exit event is unhandled, and the fresh
   draft is never surfaced to the caller.

This is a data-correctness violation: the caller receives a draft that was not produced
by the current agent invocation.

The early-exit scenario this code aims to handle (PTY exits before the JS listener can
match) is eliminated by the V1 fix — once `tabId` is used directly in the listener,
there is no null window and the listener correctly handles all exits including fast ones.

**Required fix:**
- Delete lines 70-76 entirely (the early-exit check block, including its comment).

---

## Already Fixed (do not re-flag)

- Norm path: `filePath.replace(/\\/g, '/')` present at line 46. Resolved.
- Register-before-spawn: `onExit` registered at line 57, `spawn` called at line 65. Correct.
- All buttons carry `type="button"`. No new violations.
- No inline `style={{}}` props. No new violations.
- No new IPC channels. Existing channels only.
- `content.trim().length > 0` guard on `onDraftReady`. Correct.
