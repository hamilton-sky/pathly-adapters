# Studio AI Chat — Edge Cases

## Category 1: Ollama / phi4-mini Offline

### EC-1.1: Ollama not running
- **Trigger:** User sends message; Ollama daemon not running on :11434
- **Expected:** MatchCard still appears (embedding is unaffected). Explanation area shows
  inline message: *"Ollama offline — explanation unavailable. Install: `winget install Ollama.Ollama`"*
- **Key:** MatchCard must render even without phi4-mini. Explanation is a nice-to-have, routing is required.
- **Handled in:** Conv 1, Phase 2 — wrap Ollama call in try/except, return graceful response

### EC-1.2: Requested model not pulled
- **Trigger:** `PATHLY_CHAT_MODEL=phi4-mini` but `ollama pull phi4-mini` was never run
- **Expected:** `/chat` returns `{ "error": "Model 'phi4-mini' not found — run: ollama pull phi4-mini" }`
- **Handled in:** Conv 1, Phase 2 — catch `ollama.ResponseError`

---

## Category 2: MiniLM / Embedding Issues

### EC-2.1: MiniLM model not yet loaded when user sends first message
- **Trigger:** User types a message before startup pre-embedding completes
- **Expected:** Show `◈ Loading model…` in MiniLM pill; disable send button until `embedReady: true`
- **Handled in:** Conv 5, Phase 17 — check `embedReady` in ChatInput before calling matchIntent()

### EC-2.2: No skill matches above threshold
- **Trigger:** User types something with no relation to Pathly skills (e.g. "what's the weather?")
- **Expected:** All scores < 40%; show message: *"I couldn't match that to a Pathly skill. Try rephrasing or pick a skill from the panel above."* No MatchCard rendered.
- **Handled in:** Conv 5, Phase 18 — check top score before rendering MatchCard

### EC-2.3: All skills have identical/missing descriptions
- **Trigger:** skills.json has empty or one-word descriptions
- **Expected:** Matches will be low quality and low confidence. System still works (amber cards shown).
- **Mitigation:** Each skill in skills.json must have a specific 1–2 sentence description — document this requirement in skills.json comments.

---

## Category 3: IPC / Terminal Write

### EC-3.1: No active PTY tab when Run is clicked
- **Trigger:** User has no terminal tabs open (or never opened one) and clicks Run in MatchCard
- **Expected:** IPC handler auto-spawns a new terminal tab for the target CLI (Claude Code or Codex),
  waits for it to be ready, then writes the command. IPC returns `{ ok: true, spawned: true }`.
  ChatPanel shows a brief hint: *"Opened a Claude Code tab to run this command."*
  The new terminal tab becomes visible in the terminal area so the user can watch execution.
- **Key:** The user never needs to manually open a terminal. The Conductor is the primary interface.
- **Fallback:** If tab creation fails (e.g. CLI binary not found), return `{ error: "Could not open terminal — is Claude Code installed?" }`
- **Handled in:** Conv 3, Phase 11 — auto-spawn in IPC handler before write

### EC-3.2: Active tab is wrong CLI
- **Trigger:** User has Codex tab active but the skill should run in Claude Code
- **Expected:** In Manual mode, user sees which terminal the command will write to in the MatchCard.
  They can switch tabs before clicking Run. System writes to whichever tab is currently active.
- **Note:** The system does not auto-switch tabs — that would be unexpected.

### EC-3.3: Command string contains injection characters
- **Trigger:** A malicious or hallucinated command with `; rm -rf /` appended
- **Expected:** Strip `;`, `&&`, `||`, `|`, `>`, `<` from command string before IPC write.
  Log warning in main process.
- **Handled in:** Conv 3, Phase 11 — sanitize in IPC handler before `pty.write()`

---

## Category 4: Context / FSM

### EC-4.1: FSM server not running
- **Trigger:** `pathly-fsm-http` never started; context fetch to :8765 fails
- **Expected:** `buildPathlyContext()` catches the error; sends context with `fsmStage: "unknown"`.
  phi4-mini notes it can't read the stage.
- **Handled in:** Conv 4, Phase 12

### EC-4.2: Plan file too large
- **Trigger:** FEATURE_INDEX.md has 5,000+ tokens
- **Expected:** Truncated to fit within 1,000 token cap; `[...truncated]` appended
- **Handled in:** Conv 1, Phase 3 — truncate in chat_tools.py

---

## Category 5: UI / Streaming

### EC-5.1: User clicks "Not this" on a low-confidence match
- **Trigger:** MatchCard shows `~ UNSURE`, user clicks "Not this"
- **Expected:** MatchCard is cleared from message list. Input refocuses with placeholder
  "Try rephrasing…". No command is sent.
- **Handled in:** Conv 3, Phase 9

### EC-5.2: User clicks alternative skill chip
- **Trigger:** MatchCard shows alts `[/pathly plan 34%]`, user clicks it
- **Expected:** Current MatchCard is replaced with a new MatchCard for `/pathly plan`.
  phi4-mini re-explains for the new skill. Skills panel updates highlight.
- **Handled in:** Conv 3, Phase 9

### EC-5.3: User stops phi4-mini stream mid-explanation
- **Trigger:** User clicks Stop (■) while explanation is streaming
- **Expected:** `abortController.abort()` called; partial explanation kept with `[stopped]` marker.
  MatchCard is already rendered and unaffected — user can still click Run.
- **Handled in:** Conv 2, Phase 8

### EC-5.4: PTY output contains ANSI escape codes
- **Trigger:** Claude Code outputs coloured/formatted terminal text
- **Expected:** Strip ANSI codes before displaying in OutputSnippet (use `strip-ansi` or equivalent)
- **Handled in:** Conv 3, Phase 10

---

## Known Limitations (accepted for v1)
- Chat history stored in localStorage only — lost on browser data clear
- Panel width fixed at 300px — not resizable
- Auto-approve disabled for matches < 65% confidence regardless of setting
- phi4-mini explanation quality depends on Ollama model version and available RAM
- OutputSnippet shows only last 5 PTY lines — no scroll history
