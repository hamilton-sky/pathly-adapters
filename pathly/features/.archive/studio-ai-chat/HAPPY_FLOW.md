# Studio AI Chat — Happy Flow

## Overview

A developer opens Pathly Studio mid-pipeline, unsure what to do next. They open the Conductor
chat panel, type what they want in plain English, see the right Pathly skill matched instantly,
read a 2-sentence explanation from phi4-mini, click Run, and the skill executes in the Claude Code
terminal — all without typing a single CLI command, remembering a skill name, or ever manually
opening a terminal tab. The Conductor is the only interface they need to touch.

---

## Step-by-Step Happy Flow

### Step 1: Studio opens with Conductor panel visible — no terminal required
- **User does:** Launches Pathly Studio with feature `studio-ai-chat` at stage `plan_complete`. No terminal tab is open.
- **System does:** Studio loads; ChatPanel is visible (300px right sidebar); SkillsPanel shows 14 skill chips; MiniLM pre-embeds all skills in background. **Terminal area is empty — that's fine.**
- **State after:** `embedReady: true`, all skill vectors in memory, phi4-mini warming up in Ollama

### Step 2: User types plain-English intent
- **User does:** Clicks the input bar, types "my plan is ready, I want to start building", presses Enter
- **System does:**
  1. User message appears in MessageList immediately
  2. `matchIntent()` runs — MiniLM embeds the input, cosines against 14 skill vectors
  3. Top match: `/pathly build` at 92% confidence (< 22ms)
  4. POST /chat fires to Python server (async — doesn't block MatchCard)
- **State after:** `currentMatch: { skill: "build", command: "/pathly build", score: 0.92 }`

### Step 3: MatchCard renders instantly
- **User does:** Sees the MatchCard appear almost immediately (< 50ms after send)
- **System does:**
  1. MatchCard shows: `✓ MATCHED · 92%`, `/pathly build`, skill description, `$ /pathly build` command, alternatives `[/pathly plan 34%]`
  2. `build` chip highlights green in SkillsPanel
  3. phi4-mini streams explanation (2–3 seconds): *"Your plan is complete — /pathly build is the right next step. It will spawn the builder agent and work through your IMPLEMENTATION_PLAN.md conversation by conversation."*
- **State after:** MatchCard visible, explanation streaming below it

### Step 4: User clicks Run — terminal opens automatically
- **User does:** Reads explanation, confirms it makes sense, clicks `▶ Run`
- **System does:**
  1. ChatPanel reads `chatStore.targetKind` — set to `'claude'` (ConductorHeader pill)
  2. Looks up `terminalStore.tabs` — no Claude Code tab found
  3. **Calls `launchTerminal('claude')`** — opens the terminal dock, calls `addTab()`, calls `window.pathly.terminal.spawn()`
  4. `window.pathly.terminal.write(tabId, '/pathly build\n')` — renderer-side, no new IPC
  5. Claude Code tab becomes visible in the terminal area — user can see it running
  6. ChatPanel shows hint: *"Opened a Claude Code tab to run this command."*
  7. MatchCard dims to `✓ Sent` state
  8. OutputSnippet appears — starts reading `window.pathly.terminal.onData` events
- **State after:** Terminal running `/pathly build`, OutputSnippet showing live lines, Claude Code CLI pill pulsing

### Step 5: Build runs, output feeds back
- **User does:** Watches the OutputSnippet in the chat panel while build runs
- **System does:**
  1. OutputSnippet shows last 5 PTY lines in real-time
  2. Claude Code CLI pill pulses (active); Codex pill dims (idle)
  3. Build completes: PTY signals done
- **State after:** OutputSnippet status → `✓ Done`, FSM stage advances to `build_complete`

### Step 6: AI suggests next step automatically
- **User does:** Sees a new message appear without typing anything
- **System does:**
  1. System reads last PTY lines, extracts completion signal
  2. `matchIntent("build complete, stage is build_complete")` runs
  3. Top match: `/pathly review` at 88%
  4. New MatchCard appears: `✓ MATCHED · 88% · /pathly review`
  5. phi4-mini explains: *"Build finished successfully. The next step is code review — /pathly review will run the adversarial reviewer on your changes."*
- **State after:** User can click Run again for review, or ask a follow-up question

---

## End State

The user completed `plan_complete → build_complete → review` without typing a single CLI command.
The Conductor panel guided the entire sequence from one place.

## Success Indicators
- [ ] MatchCard appears within 50ms of message send
- [ ] Correct skill matched for all 5 common test phrases (see S5.2 acceptance criteria)
- [ ] Run executes in terminal within 200ms of click
- [ ] OutputSnippet shows live lines with no more than 500ms lag
- [ ] Automatic next-step suggestion appears after command completes
- [ ] `~ UNSURE` state appears when intent is ambiguous

---

## Happy Flow 2: UI Automation — Create a Flow from Plain English

A developer wants to create a new BrightSky workflow but doesn't want to manually navigate the Studio forms.

### Step 1: User describes the flow they want

- **User does:** Types "create a checkout flow with an HTTP step to Stripe and a condition step"
- **System does:**
  1. `buildPathlyContext()` runs — includes `studioSchema` describing all key Studio UI elements
  2. POST /chat fires with `mode: 'automation'` and the studio schema
  3. AI (WebLLM model) reads the schema: sees "New Flow" button (FlowEditor), flow name input, step type selector (StepEditor)
  4. AI generates a structured action plan: 5 steps covering create → name → add HTTP → configure → add condition
- **State after:** `automationStore.steps` populated with 5 steps, `AutomationCard` appears in chat

### Step 2: AutomationCard shows the plan

- **User does:** Reads the AutomationCard: *"Checkout flow — 5 steps: create flow, name it, add HTTP step, set URL, add condition step"*
- **System does:** Renders `AutomationCard` with intent summary, step count, `[▶ Run All]` and `[Step by Step]` buttons
- **User does:** Clicks `[Step by Step]` (wants to review each action)
- **State after:** `automationStore.mode = 'staged'`, StepQueue renders with step 1 highlighted

### Step 3: Staged execution — step by step

- **User does:** Reads step 1 card: *"Click 'New Flow' button"* — clicks `[✓ Approve]`
- **System does:** `window.electronAPI.executeAutomationStep({ type: 'click', label: 'New Flow', screen: 'FlowEditor' })` — Playwright resolves the element and clicks it. New flow modal opens in Studio.
- **User does:** Reads step 2: *"Fill flow name with 'Checkout Flow'"* — clicks `[✓ Approve]`
- **System does:** `window.electronAPI.executeAutomationStep({ type: 'fill', label: 'Flow Name', value: 'Checkout Flow' })` — Playwright fills the input. User can see it update in the open modal.
- **... continues through 3 more steps ...**
- **State after:** All 5 steps executed, flow "Checkout Flow" exists in Studio with correct structure

### Step 4: Completion

- **User does:** Sees summary in chat: *"Done — Checkout Flow created with 2 steps (HTTP → Stripe, Condition)."* Sees the new flow highlighted in the Studio canvas.
- **System does:** All steps marked `done` in StepQueue. AI sends a summary message. StepQueue shows all steps dimmed with `✓` badges.

### End State

The user described a flow in one sentence and the AI built it in Studio — no menu navigation, no form-filling, no step type memorization.

**Success indicators for Flow 2:**
- [ ] AutomationCard appears after user describes a flow
- [ ] Each staged step executes on approve and shows visual feedback (element flash)
- [ ] Flow exists in Studio after all steps complete
- [ ] Summary message appears with correct step count
- [ ] `[■ Stop]` in auto mode halts immediately

---

## Happy Flow 3: Model Selection — Pick and Use a New Model

A developer wants better code-related explanations and decides to switch to Qwen2.5 Coder 7B.

### Step 1: Open model selector

- **User does:** Clicks the model pill in ConductorHeader — currently showing `Phi-4 Mini`
- **System does:** ModelSelector dropdown opens showing 4 model cards with specs, `Recommended` badge on Phi-4 Mini, `Cached` badge on Phi-4 Mini (already downloaded)

### Step 2: Download and cache a new model

- **User does:** Expands Qwen2.5 Coder 7B card — reads SYSTEM/STORAGE/SPEED specs. Toggles Cache on.
- **System does:** `cacheWebLLMModel('Qwen2.5-Coder-7B-Instruct-q4f16_1-MLC', onProgress)` — progress bar appears. `modelStore.setProgress(id, pct)` updates every few seconds.
- **User does:** Waits while it downloads (~5GB). Can use Studio normally during download.
- **System does:** Download completes. `Cached` badge appears on Qwen2.5 Coder 7B card.

### Step 3: Select the model

- **User does:** Clicks Qwen2.5 Coder 7B card to select it
- **System does:** `modelStore.setSelectedModel(id)`. ConductorHeader pill updates to show `Qwen2.5 Coder`. `getEngine(id)` initializes the WebLLM engine with the new model.

### Step 4: Use the model

- **User does:** Types "my plan is ready, time to build"
- **System does:** `askWebLLM(prompt, systemPrompt, onChunk)` — response streams from Qwen2.5 Coder 7B. Explanation is more code-specific than Phi-4 Mini's response.

**Success indicators for Flow 3:**
- [ ] Model selector opens from header pill
- [ ] Download progress visible and accurate
- [ ] Model switch takes effect on next message (not mid-stream)
- [ ] Selection persists after app restart
