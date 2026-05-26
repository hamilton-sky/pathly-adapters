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

## Category 6: Page Analyzer

### EC-6.1: Element registered but DOM node removed before action
- **Trigger:** AI generates action for `btn-add-step` but user navigated away before execution
- **Expected:** `window.__uiExecutor.execute()` returns `{ ok: false, error: 'element not found' }`. StepQueue marks step as `error`, shows inline message "Element not found — page may have changed". User can retry or skip.
- **Handled in:** Conv 7, Phase 23

### EC-6.2: No components registered (empty registry)
- **Trigger:** AI requests page context but no Studio components call `usePageAnalyzer` yet (Conv 6 incomplete)
- **Expected:** `getPageContext()` returns `{ elements: [], timestamp }`. AI context section reads "No UI elements registered." AI still responds but cannot generate action steps.
- **Handled in:** Conv 6, Phase 20

### EC-6.3: Too many elements registered
- **Trigger:** A complex flow editor view has 80+ interactive elements
- **Expected:** `getPageContext()` caps at 50 elements, prioritizes by type: input > button > select > panel > link. Truncated count noted in context: "20 more elements not shown."
- **Handled in:** Conv 6, Phase 20

### EC-6.4: React controlled input — value doesn't update after fill
- **Trigger:** `executeAction({ type: 'fill', ... })` sets `.value` but React's onChange never fires
- **Expected:** Action executor dispatches both `input` and `change` synthetic events after setting value. React reconciler picks up the state change.
- **Handled in:** Conv 7, Phase 23 — use `nativeInputValueSetter` trick for React controlled inputs

---

## Category 7: Action Executor

### EC-7.1: AI generates action for a disabled element
- **Trigger:** AI tries to click "Save" but it's disabled (form validation not passed)
- **Expected:** `executeAction` detects `element.disabled === true`, returns `{ ok: false, error: 'element disabled' }`. StepQueue shows "Save is disabled — complete required fields first." Staged mode pauses; auto mode stops and shows error.
- **Handled in:** Conv 7, Phase 23

### EC-7.2: Action sequence partially completes before error
- **Trigger:** Steps 1–3 succeed (flow created, named), step 4 fails (step type selector not found)
- **Expected:** Auto mode stops at step 4 and shows "Stopped at step 4 — element not found". Previously completed steps remain done. User can resume from step 4 in staged mode.
- **Handled in:** Conv 8, Phase 26 — `automationStore` tracks per-step status; resume picks up from last non-done step

### EC-7.3: User edits a field after AI filled it
- **Trigger:** AI fills "Flow Name" with "Checkout Flow", user overwrites it with "Payment Flow" mid-staged-mode
- **Expected:** No conflict. The fill was a one-shot action. The user's edit is the current value. If AI tries to fill the same field again in a later step, it overwrites the user's value — this is expected (user should have skipped the step if they wanted their value).

---

## Category 8: Staged / Auto Mode

### EC-8.1: User cancels auto mode mid-sequence
- **Trigger:** Auto mode running, user clicks `[■ Stop]` after step 3 of 7
- **Expected:** Execution halts immediately after current action completes (no mid-action cancellation). Steps 4–7 remain `pending`. Summary message: "Stopped at step 3 — 4 steps not executed." User can restart in staged mode.
- **Handled in:** Conv 8, Phase 26 — `automationStore.status` set to `'paused'` on stop

### EC-8.2: AI generates an action step with no matching element ID
- **Trigger:** AI hallucinates an element ID that doesn't exist in the registry (e.g. `btn-submit` when registry has `btn-save`)
- **Expected:** `executeAction` returns `{ ok: false, error: 'element not found' }`. For staged mode: shows error + "This step couldn't find the right button. Skip or retry?" For auto mode: stops and reports.
- **Mitigation:** AI system prompt includes the full `pageContext` element list — AI must only reference IDs from that list. Non-existent IDs are a hallucination that context injection should prevent.
- **Handled in:** Conv 8, Phase 26

### EC-8.3: Auto mode runs when no page context is available
- **Trigger:** User requests "create a flow" before Conv 6 page analyzer is implemented
- **Expected:** If `pageContext.elements.length === 0`, `[▶ Run All]` is disabled. Tooltip: "No UI elements registered — page analyzer required."
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
- Action executor supports click/fill/select only — no drag-and-drop or keyboard shortcuts
- Ollama backend is optional/legacy — not required for Conv 9+ (WebLLM is default)
