# Studio AI Chat — Edge Cases

## Category 1: AI Model Offline / Not Ready

> Note: Ollama is now optional. WebLLM (`@mlc-ai/web-llm`) is the default backend from Conv 9.
> Edge cases below cover both backends.

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

---

## Category 6: Static Studio Schema

### EC-6.1: AI references a label not in the schema
- **Trigger:** AI generates a step with `label: 'Submit'` but that label isn't in `studioSchema.ts`
- **Expected:** Playwright cascade tries `getByText('Submit', { exact: false })` as a final fallback. If still not found, step returns `{ ok: false, error: 'element not found: Submit' }`. StepQueue shows inline error. User can skip or retry.
- **Handled in:** Conv 7, Phase 21 — getByText fallback in resolveElement cascade

### EC-6.2: Studio adds a new screen or component not in schema
- **Trigger:** Developer adds a new modal or panel to Studio that isn't described in `studioSchema.ts`
- **Expected:** Any step targeting that screen's elements fails with "element not found". Fix path: add the new screen's elements to `studioSchema.ts` — one file, one edit, no runtime changes needed.
- **Handled in:** Conv 6, Phase 19 — schema is the single source of truth

### EC-6.3: Schema has a wrong label for an element
- **Trigger:** `studioSchema.ts` describes a button as "New Flow" but the actual button text is "Create Flow"
- **Expected:** Playwright cascade tries role → label → placeholder → text (partial match). The `getByText('New Flow', { exact: false })` strategy may still match if "New Flow" appears as part of the button's accessible name. Worst case: clean error with the label that wasn't found — no silent failure.
- **Handled in:** Conv 7, Phase 21 — cascade provides automatic resilience

---

## Category 7: Playwright Executor

### EC-7.1: CDP connection fails (app restarted without reinitializing)
- **Trigger:** Studio app is restarted but `playwrightExecutor` singleton was not reconnected
- **Expected:** On next `executeStep` call, executor detects `this.page === null` and returns `{ ok: false, error: 'Playwright not connected' }`. StepQueue shows "Automation unavailable — restart Studio". Reconnect can be triggered manually or on next app start.
- **Handled in:** Conv 7, Phase 21 — null check in executeStep

### EC-7.2: Element found but disabled
- **Trigger:** AI tries to click "Save" but it's disabled (form validation not passed)
- **Expected:** `locator.isDisabled()` returns true. Step returns `{ ok: false, error: 'element disabled: Save' }`. StepQueue shows "Save is disabled — complete required fields first." Staged mode pauses; auto mode stops and shows error.
- **Handled in:** Conv 7, Phase 21 — isDisabled check before executing action

### EC-7.3: Multiple elements match the same label
- **Trigger:** Two buttons both have accessible name "Save" on the same page
- **Expected:** Playwright's `.first()` is used as tiebreaker — the first matching element in DOM order is acted on. A warning is logged with the match count. No crash.
- **Handled in:** Conv 7, Phase 21 — `loc.first()` in resolveElement

### EC-7.4: Fill on a React controlled input
- **Trigger:** `executeStep({ type: 'fill', label: 'Flow Name', value: 'Checkout Flow' })`
- **Expected:** Playwright's `.fill()` triggers React synthetic events correctly — unlike raw DOM value assignment, Playwright dispatches the correct input events that React's synthetic event system picks up. No special handling needed.
- **Handled in:** Conv 7, Phase 21 — Playwright `.fill()` handles this natively

### EC-7.5: Playwright not installed
- **Trigger:** `@playwright/test` is missing from `studio/package.json` or browsers not downloaded
- **Expected:** Import fails at startup. Electron logs a clear error: "Playwright not available — automation disabled". All `executeStep` calls return `{ ok: false, error: 'Playwright not connected' }`. Skill routing (MatchCard) is unaffected.
- **Handled in:** Conv 7, Phase 21 — startup check logs warning; automation disabled gracefully

---

## Category 8: Staged / Auto Mode

### EC-8.1: User cancels auto mode mid-sequence
- **Trigger:** Auto mode running, user clicks `[■ Stop]` after step 3 of 7
- **Expected:** Execution halts immediately after current action completes (no mid-action cancellation). Steps 4–7 remain `pending`. Summary message: "Stopped at step 3 — 4 steps not executed." User can restart in staged mode.
- **Handled in:** Conv 8, Phase 26 — `automationStore.status` set to `'paused'` on stop

### EC-8.2: AI generates an action step with a label not in the schema
- **Trigger:** AI hallucinates a label that doesn't exist in `studioSchema.ts` (e.g. `label: 'Submit'` when schema has `'Save'`)
- **Expected:** `PlaywrightExecutor.executeStep` tries the full cascade including `getByText` fuzzy match. If nothing found, returns `{ ok: false, error: 'element not found: Submit' }`. Staged mode shows error + "This step couldn't find the right element. Skip or retry?" Auto mode stops and reports.
- **Mitigation:** AI system prompt lists all labels from `studioSchema` and instructs the AI to use only those labels. Label hallucination should be rare when schema is injected correctly.
- **Handled in:** Conv 8, Phase 26

### EC-8.3: Auto mode runs before studioSchema is available
- **Trigger:** User requests "create a flow" before Conv 6 static schema is implemented
- **Expected:** If `studioSchema` is missing from context, `[▶ Run All]` is disabled. Tooltip: "Studio schema not loaded — Conv 6 required."
- **Handled in:** Conv 8, Phase 25

---

## Category 9: WebLLM / Model Selector

### EC-9.1: WebGPU not available in the user's Electron/Chrome version
- **Trigger:** User's GPU or driver doesn't support WebGPU
- **Expected:** `CreateMLCEngine()` throws. `webLLMEngine.ts` catches it and returns `{ error: 'WebGPU not supported on this device' }`. ModelSelector shows "WebGPU required — upgrade your driver or use Ollama backend." Falls back to Ollama if configured.
- **Handled in:** Conv 9, Phase 27

### EC-9.2: Model download interrupted (network cut mid-download)
- **Trigger:** User starts caching Qwen3 4B (~3GB), network drops at 60%
- **Expected:** Progress bar shows last known percentage. On reconnect, `cacheWebLLMModel()` resumes from where it left off (WebLLM handles resume internally). If app is closed mid-download, partial cache is cleared on next open — user must restart download.
- **Handled in:** Conv 9, Phase 27

### EC-9.3: Selected model is not cached when user sends a message
- **Trigger:** User selects Qwen2.5 Coder 7B but hasn't cached it yet
- **Expected:** ChatInput send button is disabled. Input placeholder: "Download Qwen2.5 Coder 7B to continue." ModelSelector shows the selected model with a "Download required" state. Clicking the Cache toggle in ModelSelector starts the download.
- **Handled in:** Conv 9, Phase 28

### EC-9.4: Switching model mid-conversation
- **Trigger:** User switches from Phi-4 Mini to Qwen3 4B while a message is streaming
- **Expected:** Current stream completes on Phi-4 Mini. Next message uses Qwen3 4B. No hard reset of conversation history — history is passed to the new model.
- **Handled in:** Conv 9, Phase 29

---

## Known Limitations (accepted for v1)
- Chat history stored in localStorage only — lost on browser data clear
- Panel width fixed at 300px — not resizable
- Auto-approve disabled for matches < 65% confidence regardless of setting
- WebLLM model quality depends on selected model and device GPU capability
- OutputSnippet shows only last 5 PTY lines — no scroll history
- Playwright executor supports click/fill/select only — no drag-and-drop or keyboard shortcuts
- Ollama backend is optional/legacy — not required for Conv 9+ (WebLLM is default)
