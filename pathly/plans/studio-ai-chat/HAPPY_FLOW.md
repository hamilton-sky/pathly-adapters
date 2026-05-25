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
  1. IPC `chat:write-terminal` fires with `{ command: "/pathly build", target: "claude-code" }`
  2. Electron main checks `activePtys` — no Claude Code tab found
  3. **Auto-spawns a new "A Claude" terminal tab** (same as clicking +, selecting Claude Code)
  4. Waits for PTY ready signal, then writes `/pathly build\n`
  5. Claude Code tab becomes visible in the terminal area — user can see it running
  6. IPC returns `{ ok: true, spawned: true }`
  7. ChatPanel shows hint: *"Opened a Claude Code tab to run this command."*
  8. MatchCard dims to `✓ Sent` state
  9. OutputSnippet appears — starts reading PTY `onData` events
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
