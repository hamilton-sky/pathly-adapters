# Studio AI Chat — Edge Cases

## Category 1: Ollama Not Available

### EC-1.1: Ollama is not installed or not running
- **Trigger:** User sends a message but Ollama daemon is not running on :11434
- **Current behavior:** fetch to Ollama times out; Python server crashes or hangs
- **Expected behavior:** `/chat` returns 503 with `{"error": "Ollama not available"}` within 3 seconds; ChatPanel shows an inline error message "AI model offline — start Ollama to continue"
- **Handled in:** Phase 2 / Conv 1 — wrap Ollama call in try/except, return 503

### EC-1.2: Requested model not pulled
- **Trigger:** `PATHLY_CHAT_MODEL=llama3` but user never ran `ollama pull llama3`
- **Current behavior:** Ollama returns model-not-found error
- **Expected behavior:** `/chat` returns 503 with `{"error": "Model 'llama3' not found — run: ollama pull llama3"}`
- **Handled in:** Phase 2 / Conv 1 — catch `ollama.ResponseError`, extract model name from error message

---

## Category 2: Context Overflow

### EC-2.1: Plan file is very large
- **Trigger:** Active feature plan has 5,000+ tokens in FEATURE_INDEX.md
- **Current behavior:** System prompt exceeds 2,000 token cap
- **Expected behavior:** Plan summary is truncated to fit within the cap; truncation marker appended: `[...truncated]`
- **Handled in:** Phase 3 / Conv 1 — token-count plan summary before injecting, truncate at character boundary

### EC-2.2: PageAnalyzer returns hundreds of elements
- **Trigger:** Studio has many UI elements visible (large plan board, many buttons)
- **Current behavior:** Screen context exceeds 500 token budget
- **Expected behavior:** Truncate elements list to first 20 buttons + 10 forms + 10 text blocks; skip the rest
- **Handled in:** Phase 11–12 / Conv 4 — cap arrays in pathlyContext.ts before serialization

---

## Category 3: Streaming Interruption

### EC-3.1: User stops stream mid-response
- **Trigger:** User clicks Stop button while AI is mid-sentence
- **Current behavior:** undefined — reader continues in background, store gets partial updates
- **Expected behavior:** `reader.cancel()` is called; `setStreaming(false)`; partial message is kept in store as-is with a `[stopped]` marker
- **Handled in:** Phase 6 / Conv 2 — Stop button calls `abortController.abort()`, message content frozen

### EC-3.2: FSM server not running during context fetch
- **Trigger:** `pathly-fsm-http` was never started; `buildPathlyContext()` fetch to :8765 fails
- **Current behavior:** Unhandled promise rejection; message send may fail entirely
- **Expected behavior:** Context is sent with `fsmStage: "unknown"` — AI still responds but notes it can't read the pipeline state
- **Handled in:** Phase 11 / Conv 4 — wrap FSM fetch in try/catch, fallback to `{ fsmStage: "unknown" }`

---

## Category 4: IPC / Terminal Write

### EC-4.1: No active PTY tab when command is approved
- **Trigger:** User closes all terminal tabs then approves a command
- **Current behavior:** `activePtys.get(activeTabId)` returns undefined; silent failure
- **Expected behavior:** IPC handler returns `{ error: "No terminal open" }`; ChatPanel shows toast "Open a terminal tab first"
- **Handled in:** Phase 8 / Conv 3 — check for undefined PTY, return error to renderer

### EC-4.2: Command contains shell injection characters
- **Trigger:** AI hallucinates a command with `; rm -rf /` appended
- **Current behavior:** Would execute destructively if auto-approved
- **Expected behavior:** In manual mode, user sees the full command and can dismiss. In auto mode: strip any `;`, `&&`, `||`, `|`, `>` characters before writing — or disable auto-approve for commands longer than 80 chars
- **Handled in:** Phase 9 / Conv 3 — sanitize command string in TerminalApproval before invoking IPC

---

## Known Limitations
- Chat history is stored in localStorage only — no disk persistence, lost on browser data clear
- PageAnalyzer only reads the Studio renderer DOM, not external browser windows
- Ollama model quality varies; phi4-mini may misidentify FSM stages on first try
- Auto-approve is per-session only in Conv 3; cross-session persistence added in Conv 3 via Zustand persist
