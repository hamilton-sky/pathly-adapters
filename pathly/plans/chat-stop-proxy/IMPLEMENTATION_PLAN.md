# Implementation Plan — chat-stop-proxy

---

## Pre-flight — Phase 0 (Conv 0)

**Stories:** none (baseline verification)

**Purpose:** Record the live state of every file touched by this feature before
any changes are made. Any pre-existing failures are baseline debt, not
regressions introduced by this feature.

**Verify steps:**
1. Confirm file paths exist:
   - `studio/src/renderer/src/components/ChatPanel/ChatInput.tsx`
   - `studio/src/renderer/src/components/ChatPanel/index.tsx`
   - `studio/src/renderer/src/store/chatStore.ts`
   - `studio/src/renderer/src/lib/llmBridge.ts`
   - `studio/src/renderer/src/lib/launchTerminal.ts`
2. Confirm `abortLlm()` exists in `llmBridge.ts` and calls `window.pathly.llm.abort()`.
3. Confirm `chatStore` has `isLoading`, `setLoading`, `updateLastMessage`,
   `outputByTarget`, `setCommandRunning`, `appendOutputLine`.
4. Confirm `ChatInput` props signature: `{ value, onChange, onSend, disabled? }`.
5. Record any TypeScript errors present before changes begin.

**File:** `pathly/plans/chat-stop-proxy/PROGRESS.md`
**Done when:** PROGRESS.md is updated with pre-flight results and no unresolved blockers found.

---

## Conv 1 — Stop Button

**Stories:** S-01, S-02, S-03

### Phase 1.1 — UI/UX design pass (ui-ux-pro-max)

**File:** `studio/src/renderer/src/components/ChatPanel/ChatInput.tsx`
**Done when:** Design spec for Stop button (icon, color treatment, size, position) is approved
and recorded in the conversation before any code is written.

Design constraints:
- Icon: Lucide `<Square>` (stop), same size-13 as `<Send>`
- Color: distinct from Send — use a muted accent or destructive treatment from existing palette
- No layout shift — button occupies same position as Send
- Enabled at all times when `isLoading === true`

### Phase 1.2 — ChatInput: add `isLoading` + `onStop` props

**File:** `studio/src/renderer/src/components/ChatPanel/ChatInput.tsx`

Changes:
- Add `isLoading?: boolean` and `onStop?: () => void` to props interface (lines 8-13).
- When `isLoading === true`: render `<Square>` icon; button `onClick` calls `onStop()`; button
  is always enabled (override `disabled` logic).
- When `isLoading === false`: existing `<Send>` render and disabled logic unchanged.
- Block Enter key submission when `isLoading === true` (add guard in `onKeyDown`).

**Done when:** `ChatInput` renders `<Square>` when `isLoading=true` and `<Send>` otherwise;
Enter is blocked during loading; no TypeScript errors.

### Phase 1.3 — ChatPanel: wire `isLoading` and `onStop` into ChatInput

**File:** `studio/src/renderer/src/components/ChatPanel/index.tsx`

Changes:
- Pass `isLoading` from `chatStore` to `<ChatInput>`.
- Implement `handleStop()`:
  ```
  function handleStop() {
    abortLlm()
    updateLastMessage({ status: 'done' })
    setLoading(false)
  }
  ```
- Pass `onStop={handleStop}` to `<ChatInput>`.

**Done when:** Clicking Stop during a live stream calls `abortLlm`, sets `status: 'done'`,
sets `isLoading: false`; no orphaned `streaming` state remains in store.

### Phase 1.4 — Verify Conv 1

Verify S-01, S-02, S-03 acceptance criteria:
- AC-01a through AC-01d: visual transform confirmed in renderer.
- AC-02a through AC-02e: stop mechanics verified including race and pre-token cases.
- AC-03a through AC-03c: partial text preserved, no streaming state remains.

**Done when:** Write `pathly/plans/chat-stop-proxy/VERIFY.md` with first line
`RESULT: PASS` and a one-line summary of what was verified.

---

## Conv 2 — Claude Code Proxy

**Stories:** S-04, S-05, S-06

### Phase 2.1 — UI/UX design pass (ui-ux-pro-max)

**File:** `studio/src/renderer/src/components/ChatPanel/ChatInput.tsx`
**Done when:** Design spec for mode toggle (placement, segmented control vs icon, `CC` badge
style) is approved and recorded before any code is written.

Design constraints:
- Toggle lives inline in ChatInput footer — no additional height/layout shift
- Two labeled states: `Chat LLM` | `Claude Code`
- Active state uses accent highlight; inactive is muted
- `CC` badge on assistant bubble: small, low-contrast, right-aligned on bubble header

### Phase 2.2 — chatStore: add `chatMode` field

**File:** `studio/src/renderer/src/store/chatStore.ts`

Changes:
- Add `chatMode: 'llm' | 'claude'` field, default `'llm'`.
- Add `setChatMode(mode: 'llm' | 'claude')` action.

**Done when:** `chatStore.chatMode` exists, defaults to `'llm'`, and `setChatMode` updates it
without affecting any other store fields.

### Phase 2.3 — ChatInput: add mode toggle UI

**File:** `studio/src/renderer/src/components/ChatPanel/ChatInput.tsx`

Changes:
- Add `chatMode: 'llm' | 'claude'` and `onModeChange: (mode) => void` props.
- Render a segmented control (or equivalent) in the footer area per the 2.1 design spec.
- Active/inactive state styling per design spec.

**Done when:** Toggle renders, clicking each segment calls `onModeChange` with the correct
mode value; no TypeScript errors.

### Phase 2.4 — ChatPanel: handle Claude Code routing in `handleSend`

**File:** `studio/src/renderer/src/components/ChatPanel/index.tsx`

Changes:
- Read `chatMode` from `chatStore`.
- Pass `chatMode` and `onModeChange={setChatMode}` to `<ChatInput>`.
- In `handleSend`, after input validation:
  - If `chatMode === 'claude'`:
    1. Create assistant bubble with `status: 'streaming'`.
    2. Call `writeToTerminal('claude', prompt, projectPath, ...)`.
    3. Subscribe to terminal data via `window.pathly.terminal.onData(tabId, cb)`.
    4. In callback: strip ANSI, append lines to bubble via `appendOutputLine('claude', line)`.
    5. When `outputByTarget.claude.running` transitions to `false` (idle timer fires):
       call `updateLastMessage({ status: 'done' })` + `setLoading(false)`.
    6. If `writeToTerminal` throws (terminal not launched): append recoverable error
       message to bubble, set `status: 'done'`, set `isLoading: false`.
  - If `chatMode === 'llm'`: existing `askOllama`/`askLlm` paths unchanged.
- Mode toggled mid-stream: new mode stored immediately; in-flight request completes
  under original mode.

**Done when:** Sending in `Claude Code` mode routes to PTY; output streams into bubble;
bubble closes to `done` when idle timer fires; LLM mode is unaffected.

### Phase 2.5 — Assistant bubble: `CC` badge for Claude Code responses

**File:** `studio/src/renderer/src/components/ChatPanel/index.tsx` (or bubble component)

Changes:
- When creating an assistant message in Claude Code mode, set a `source: 'claude-code'`
  field (or equivalent) on the message.
- Render a small `CC` badge in the bubble header when `source === 'claude-code'`.

**Done when:** Claude Code mode assistant bubbles display `CC` badge; LLM bubbles do not.

### Phase 2.6 — Verify Conv 2

Verify S-04, S-05, S-06 acceptance criteria:
- AC-04a through AC-04e: toggle visible, mode persists in session, mid-stream mode change safe.
- AC-05a through AC-05e: routing confirmed, error case handled, LLM mode not regressed.
- AC-06a through AC-06e: bubble created, lines stream in, ANSI stripped, done on idle, CC badge present.

**Done when:** Write `pathly/plans/chat-stop-proxy/VERIFY.md` (append or replace) with
first line `RESULT: PASS` and a one-line summary for Conv 2.

---

## Known limitations (MVP)

- Claude Code idle-timer false positives: if a long-running command produces no output
  for 12 seconds, the bubble closes prematurely. Accepted MVP limitation.
- Aborting an in-flight Claude Code command is not supported in this feature (future).
- Mode does not persist across app restarts (session-only is acceptable per PO_NOTES).
