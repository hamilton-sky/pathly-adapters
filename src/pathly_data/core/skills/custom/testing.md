---

---
# Conversation Prompts — chat-stop-proxy

---

## ## Conv 0 — Pre-flight

**Role:** builder
**Skill:** none
**Stories:** (baseline only)

Before writing any code, verify the live state of all files this feature touches.

### Steps

1. Verify these files exist (glob or read each):
   - `studio/src/renderer/src/components/HQ/ChatInput/ChatInput.tsx`
   - `studio/src/renderer/src/components/HQ/useHQ.tsx`
   - `studio/src/renderer/src/components/HQ/index.tsx`
   - `studio/src/renderer/src/store/chatStore.ts`
   - `studio/src/renderer/src/lib/llmBridge.ts`
   - `studio/src/renderer/src/lib/launchTerminal.ts`

2. Verify before edit — read each file and confirm:
   - `llmBridge.ts`: `abortLlm()` exists and calls `window.pathly.llm.abort()`.
   - `chatStore.ts`: fields `isLoading`, `setLoading`, `updateLastMessage`,
     `outputByTarget`, `setCommandRunning`, `appendOutputLine` all exist.
   - `ChatInput.tsx`: props interface includes `value`, `onChange`, `onSend`, `disabled?`.
   - `ChatPanel/index.tsx`: `handleSend` exists; `setLoading(true)` called at start,
     `setLoading(false)` called in finally blocks.

3. Record any TypeScript compile errors visible in the files (do not fix them).

4. Update `pathly/features/chat-stop-proxy/PROGRESS.md` — mark Conv 0 items complete
   and note any pre-existing issues found.

### Done when
All five files confirmed present; `abortLlm`, `chatStore` fields, and `ChatInput` props
confirmed by direct read; PROGRESS.md updated.

---

## ## Conv 1 — Stop Button

**Role:** builder
**Skill:** ui-ux-pro-max (Phase 1.1 only)
**Stories:** S-01, S-02, S-03

### Verify before edit
Read `HQ/ChatInput/ChatInput.tsx` and `HQ/useHQ.tsx` before touching either file.
Confirm the exact line ranges for the Send button and `handleSend` by reading
the live files — line numbers may have shifted since the plan was written.

### Phase 1.1 — Design pass (ui-ux-pro-max)

Before writing any code, produce a written design spec for the Stop button:
- Icon: Lucide `<Square>` size-13 (same container as `<Send>`)
- Color treatment: use a muted or destructive accent from the existing dark-theme palette —
  do not invent new colors
- Position: in-place replacement of Send button — no layout shift
- Enabled state: always clickable when `isLoading === true`
- Disabled state: normal Send disabled logic when `isLoading === false`

Get the design spec approved (or self-approved as the builder) before proceeding.

### Phase 1.2 — ChatInput

**File:** `studio/src/renderer/src/components/HQ/ChatInput/ChatInput.tsx`

Add to props interface (read the file first to find the actual line numbers):
```
isLoading?: boolean
onStop?: () => void
```

Button logic:
- When `isLoading === true`: render `<Square size={13} />`, button always enabled,
  `onClick` calls `onStop?.()`.
- When `isLoading === false`: existing `<Send>` render and disabled logic (no change).

Enter key guard:
- In the textarea `onKeyDown` handler: if `isLoading === true`, prevent default and
  return without calling `onSend`.

**Done when:** Component compiles with no TypeScript errors; `<Square>` renders when
`isLoading=true`; Enter blocked during loading.

### Phase 1.3 — Wire stop in useHQ + index

**Files:**
- `studio/src/renderer/src/components/HQ/useHQ.tsx` — add `handleStop`
- `studio/src/renderer/src/components/HQ/index.tsx` — pass `onStop` to `<ChatInput>`

Add `handleStop`:
```typescript
function handleStop() {
  abortLlm()
  updateLastMessage({ status: 'done' })
  setLoading(false)
}
```

Pass to `<ChatInput>`:
```tsx
<ChatInput
  ...
  isLoading={isLoading}
  onStop={handleStop}
/>
```

Note: `abortLlm` already exists in `llmBridge.ts` — import it if not already imported.

**Done when:** `handleStop` wired; no TypeScript errors; `isLoading` from chatStore
passed to ChatInput.

### Phase 1.4 — Verify

Manually verify (or write a dev test) for each acceptance criterion:

- AC-01a: Start a stream → confirm `<Square>` is rendered.
- AC-01b: Confirm Stop button is not disabled during streaming.
- AC-01c: Press Enter during streaming → confirm `onSend` is not called.
- AC-01d: Stream completes → confirm `<Send>` returns.
- AC-02a: Click Stop → confirm `abortLlm` was called (add a `console.log` if needed).
- AC-02b: After Stop → `chatStore.isLoading === false`.
- AC-02c: After Stop → last message `status === 'done'`.
- AC-02d: Click Stop after stream ends → no error thrown, state unchanged.
- AC-02e: Click Stop before first token → message resolves to `done`, content may be empty.
- AC-03a–03c: Partial text visible in bubble; no `streaming` state in store.

After all pass, write `pathly/features/chat-stop-proxy/VERIFY.md`:
```
RESULT: PASS
Conv 1 verified: Stop button transforms Send, aborts stream, preserves partial text, no orphaned streaming state.
```

Update `pathly/features/chat-stop-proxy/PROGRESS.md` — mark all Conv 1 items complete.

---

## ## Conv 2 — Claude Code Proxy

**Role:** builder
**Skill:** ui-ux-pro-max (Phase 2.1 only)
**Stories:** S-04, S-05, S-06

### Verify before edit
Read these files before touching any of them:
- `studio/src/renderer/src/store/chatStore.ts`
- `studio/src/renderer/src/components/HQ/ChatInput/ChatInput.tsx`
- `studio/src/renderer/src/components/HQ/useHQ.tsx`  ← handleSend lives here, NOT in index.tsx
- `studio/src/renderer/src/components/HQ/index.tsx`  ← ChatInput is mounted here
- `studio/src/renderer/src/components/HQ/MessageList/MessageList.tsx`
- `studio/src/renderer/src/lib/launchTerminal.ts`

Confirm `writeToTerminal` signature and `window.pathly.terminal.onData` usage in `useHQ.tsx`
(search for `writeToTerminal` — it was previously referenced at ChatPanel/index.tsx lines 165-199
but handleSend now lives in useHQ.tsx).

### Phase 2.1 — Design pass (ui-ux-pro-max)

Before writing any code, produce a written design spec for:
1. Mode toggle: placement in ChatInput footer, control type (segmented / icon pair),
   label text (`Chat LLM` | `Claude Code`), active/inactive styling.
2. `CC` badge: position on assistant bubble header, font size, color treatment.

Constraints:
- Toggle must not add height or cause layout shift in ChatInput.
- Active state uses existing accent color; inactive is muted.
- Badge is subtle — secondary visual, not competing with message content.

Get spec approved before proceeding.

### Phase 2.2 — chatStore

**File:** `studio/src/renderer/src/store/chatStore.ts`

Add to store state:
```typescript
chatMode: 'llm' | 'claude'
```
Default: `'llm'`.

Add action:
```typescript
setChatMode: (mode: 'llm' | 'claude') => void
```

**Done when:** `chatStore.chatMode` defaults to `'llm'`; `setChatMode('claude')` updates it;
no other store fields affected; no TypeScript errors.

### Phase 2.3 — ChatInput toggle UI

**File:** `studio/src/renderer/src/components/HQ/ChatInput/ChatInput.tsx`

Add to props interface:
```typescript
chatMode?: 'llm' | 'claude'
onModeChange?: (mode: 'llm' | 'claude') => void
```

Render toggle per Phase 2.1 design spec in the footer area.
Clicking each state calls `onModeChange` with the correct mode value.

**Done when:** Toggle renders; clicking calls `onModeChange`; no TypeScript errors.

### Phase 2.4 — Routing + prop wiring

**Files:**
- `studio/src/renderer/src/components/HQ/useHQ.tsx` — add `chatMode` branch in `handleSend`
- `studio/src/renderer/src/components/HQ/index.tsx` — pass `chatMode` and `onModeChange` down to `<ChatInput>`

1. In `useHQ.tsx`: read `chatMode` and `setChatMode` from `chatStore`. Add the `chatMode === 'claude'` branch to `handleSend` (see below).
2. In `index.tsx`: pass `chatMode={chatMode}` and `onModeChange={setChatMode}` to `<ChatInput>`.
3. In `handleSend`, after input validation, branch on `chatMode`:

**`chatMode === 'claude'` path:**
```typescript
setLoading(true)
const assistantMsg = { role: 'assistant', content: '', status: 'streaming', source: 'claude-code' }
addMessage(assistantMsg)
try {
  const tabId = await writeToTerminal('claude', prompt, projectPath, tabs, addTab, open, toggle)
  window.pathly.terminal.onData(tabId, (line) => {
    // strip ANSI (reuse existing feedBuffer sanitization)
    appendOutputLine('claude', line)
    updateLastMessage({ content: outputByTarget.claude.lines.join('\n') })
  })
  // idle timer in launchTerminal fires → setCommandRunning('claude', false)
  // watch outputByTarget.claude.running transition to false
  // when false: updateLastMessage({ status: 'done' }); setLoading(false)
} catch (err) {
  updateLastMessage({ content: 'Claude Code terminal is not available. Please open the terminal first.', status: 'done' })
  setLoading(false)
}
```

**`chatMode === 'llm'` path:** existing logic, no change.

**Mid-stream mode switch:** `chatMode` read at the moment `handleSend` is called —
subsequent mode changes do not affect in-flight requests.

**Done when:** Claude Code mode routes to PTY; output streams into bubble; error case
surfaces a recoverable message; LLM mode unaffected.

### Phase 2.5 — CC badge

**File:** `studio/src/renderer/src/components/HQ/MessageList/MessageList.tsx`

When rendering an assistant message where `source === 'claude-code'`, render a `CC` badge
in the bubble header per Phase 2.1 design spec.

**Done when:** Claude Code bubbles show `CC` badge; LLM bubbles do not.

### Phase 2.6 — Verify

Manually verify each acceptance criterion:

- AC-04a: Toggle visible with `Chat LLM` and `Claude Code` labels.
- AC-04b: Active state visually distinct.
- AC-04c: Switch to `Claude Code`, navigate away and back — mode still `Claude Code`.
- AC-04d: `chatStore.chatMode` reflects toggle state.
- AC-04e: Start a stream in LLM mode, switch toggle mid-stream — in-flight stream completes under LLM mode.
- AC-05a: Send in `Claude Code` mode — verify `writeToTerminal` called, not `askOllama`/`askLlm`.
- AC-05b: Terminal not visible — proxy still works.
- AC-05c: Terminal not launched — error message appears in bubble, app does not crash.
- AC-05d: `isLoading === true` during Claude Code response — Send button disabled.
- AC-05e: Switch back to `Chat LLM`, send — normal LLM response received.
- AC-06a: Streaming bubble created immediately on send.
- AC-06b: PTY lines appear in bubble as they arrive.
- AC-06c: No ANSI codes visible in bubble.
- AC-06d: After 12s idle, bubble closes to `done`.
- AC-06e: `CC` badge visible on Claude Code bubbles only.

After all pass, update `pathly/features/chat-stop-proxy/VERIFY.md`:
```
RESULT: PASS
Conv 2 verified: mode toggle routes to PTY, output streams into bubble, CC badge present, LLM mode unaffected.
```

Update `pathly/features/chat-stop-proxy/PROGRESS.md` — mark all Conv 2 items complete.

---

## ## Splitting rule

If a conversation touches more than one file of the same type, split into separate
conversations — one per file.
