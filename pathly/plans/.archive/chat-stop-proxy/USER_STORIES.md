# User Stories — chat-stop-proxy

_Source: PO_NOTES.md. Stories decomposed, not re-authored._

---

## Epic 1 — Stop/Abort Button

### S-01: Send button transforms to Stop during streaming

**As a** Pathly Studio developer,
**I want** the Send button to visually change to a Stop button while the LLM is generating,
**so that** I can see at a glance that I have the option to cancel.

**Acceptance criteria:**
- AC-01a: While `isLoading === true`, the button renders a `<Square>` icon (not `<Send>`).
- AC-01b: The Stop button is enabled (not disabled) during streaming regardless of input value.
- AC-01c: While `isLoading === true`, pressing Enter in the textarea does NOT trigger `onSend`.
- AC-01d: When `isLoading` returns to `false`, the button reverts to the `<Send>` icon and normal disabled logic resumes.

**Delivered by:** Conv 1

---

### S-02: Stop button aborts the in-flight LLM stream

**As a** Pathly Studio developer,
**I want** clicking Stop to immediately halt the LLM response,
**so that** I stop wasting tokens on a wrong-direction answer.

**Acceptance criteria:**
- AC-02a: Clicking Stop calls `abortLlm()` via `llmBridge`.
- AC-02b: After Stop, `isLoading` is `false` in `chatStore`.
- AC-02c: After Stop, the last message's `status` is `'done'` (not `'streaming'`).
- AC-02d: Stop clicked after the stream has already completed is a safe no-op — no errors thrown, no state corruption.
- AC-02e: Stop clicked before any tokens are received still resolves the message to `status: 'done'` with whatever partial content exists (including empty string).

**Delivered by:** Conv 1

---

### S-03: Partial response is preserved after Stop

**As a** Pathly Studio developer,
**I want** the text already received before I clicked Stop to remain visible,
**so that** I can see what the model had produced and decide if it was useful.

**Acceptance criteria:**
- AC-03a: The assistant bubble content is not cleared or reset when Stop is clicked.
- AC-03b: The bubble displays whatever tokens arrived before abort.
- AC-03c: No `streaming` status remains in `chatStore` after a Stop action — querying `chatStore.messages` shows the last message `status === 'done'`.

**Delivered by:** Conv 1

---

## Epic 2 — Chat-as-Claude-Code Proxy

### S-04: Mode toggle switches between LLM and Claude Code

**As a** Pathly Studio developer,
**I want** a toggle in the chat input area with `Chat LLM` and `Claude Code` states,
**so that** I can choose where my message is routed without leaving the chat panel.

**Acceptance criteria:**
- AC-04a: A toggle control is visible in the `ChatInput` footer area with two labeled states: `Chat LLM` and `Claude Code`.
- AC-04b: The currently active mode is visually distinct from the inactive mode (accent/highlight treatment consistent with dark theme).
- AC-04c: The selected mode persists for the session (switching panel tabs and back does not reset it).
- AC-04d: `chatStore` exposes a `chatMode: 'llm' | 'claude'` field that reflects the current toggle state.
- AC-04e: Mode toggled mid-stream — the in-flight request completes under its original mode; the new mode applies only to the next Send.

**Delivered by:** Conv 2

---

### S-05: Claude Code mode routes message to PTY terminal

**As a** Pathly Studio developer,
**I want** pressing Send in Claude Code mode to forward my message to the Claude Code terminal,
**so that** I can drive Claude Code conversationally from the chat panel.

**Acceptance criteria:**
- AC-05a: In `Claude Code` mode, `handleSend` calls `writeToTerminal` (not `askOllama` / `askLlm`).
- AC-05b: The Claude Code terminal does not need to be visible — only launched/attached.
- AC-05c: If the terminal has not been launched yet, a clear recoverable error message appears in the chat bubble (not a silent failure or crash).
- AC-05d: While `isLoading === true`, the Send button is disabled (blocks multiple rapid sends).
- AC-05e: Switching back to `Chat LLM` mode and sending restores normal Ollama/LLM routing — no regression.

**Delivered by:** Conv 2

---

### S-06: PTY output streams into the assistant bubble

**As a** Pathly Studio developer,
**I want** Claude Code's response to appear line by line in a chat bubble,
**so that** I see progress without switching to the terminal pane.

**Acceptance criteria:**
- AC-06a: An assistant bubble with `status: 'streaming'` is created when the PTY command is dispatched.
- AC-06b: Lines from PTY output are appended to that bubble as they arrive (via existing `appendOutputLine` + terminal data subscription).
- AC-06c: ANSI escape sequences are stripped before display (reuse existing terminal sanitization).
- AC-06d: When the existing 12-second idle timer fires (`outputByTarget.claude.running === false`), the bubble's `status` transitions to `'done'`.
- AC-06e: A subtle visual badge (e.g., `CC`) on the assistant bubble distinguishes Claude Code responses from LLM responses.

**Delivered by:** Conv 2
