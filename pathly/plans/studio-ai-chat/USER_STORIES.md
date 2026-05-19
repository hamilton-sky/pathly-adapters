# Studio AI Chat — User Stories

## Context

Pathly Studio is an Electron desktop app that orchestrates a development pipeline via an FSM (Finite State Machine) server. Currently, users must know which commands to run and when. This feature adds a collapsible AI chat sidebar to Studio powered by a local Ollama model — no cloud API, no internet required. The AI is aware of the current pipeline stage, the active feature plan, and what is on screen, so it can guide the user through Pathly's workflow step by step and optionally type commands directly into the embedded terminal.

---

## Stories

### Story S1.1: Chat server responds to messages via local Ollama model
**As a** Pathly Studio user, **I want** to send a message and get a response from a local AI model, **so that** I can get help without needing an internet connection or API key.

**Acceptance Criteria:**
- [ ] `POST /chat` endpoint exists on the Pathly Python server (port 8765)
- [ ] Request body: `{ "message": string, "history": Message[] }`
- [ ] Response streams text back (Server-Sent Events or chunked transfer)
- [ ] Ollama model is configurable via environment variable `PATHLY_CHAT_MODEL` (default: `phi4-mini`)
- [ ] If Ollama is not running, response is `{ "error": "Ollama not available" }` with status 503

**Delivered by:** Phase 1–2 → Conversation 1

---

### Story S1.2: AI system prompt includes active Pathly context
**As a** Pathly Studio user, **I want** the AI to know what stage I'm in and what feature I'm building, **so that** its guidance is relevant to my current work.

**Acceptance Criteria:**
- [ ] System prompt includes current FSM stage (read from `/next_action` on port 8765)
- [ ] System prompt includes active feature name and plan summary (read from `plans/$FEATURE/FEATURE_INDEX.md`)
- [ ] System prompt includes list of available Pathly skills
- [ ] System prompt is under 2,000 tokens in all normal cases

**Delivered by:** Phase 3 → Conversation 1

---

### Story S2.1: Collapsible right sidebar chat panel in Studio
**As a** Pathly Studio user, **I want** a chat panel on the right side of Studio that I can open and close, **so that** it doesn't take up space when I don't need it.

**Acceptance Criteria:**
- [ ] ChatPanel renders as a right-side flex child in Studio's body layout
- [ ] Panel has a toggle button (ChevronRight / ChevronLeft icon) to collapse/expand
- [ ] Collapsed state shows only the toggle button (~32px wide)
- [ ] Expanded width is 320px (resizable is out of scope for this plan)
- [ ] Panel open/closed state persists in Zustand `uiStore` across component remounts

**Delivered by:** Phase 5, 7 → Conversation 2

---

### Story S2.2: Messages stream in real-time
**As a** Pathly Studio user, **I want** to see the AI's response appear word by word, **so that** the interaction feels responsive and I can read while it types.

**Acceptance Criteria:**
- [ ] User message appears in the list immediately on send
- [ ] AI response streams character-by-character into the message list
- [ ] A blinking cursor indicator shows while streaming is in progress
- [ ] Stop button in ChatInput cancels an in-progress stream
- [ ] After streaming completes, the full message is stored in Zustand

**Delivered by:** Phase 4, 6 → Conversation 2

---

### Story S3.1: AI proposes terminal commands with user approval
**As a** Pathly Studio user, **I want** the AI to propose commands it thinks I should run, **so that** I can review and approve before anything is typed into my terminal.

**Acceptance Criteria:**
- [ ] When AI response contains a fenced code block starting with `$` or `/pathly`, a `TerminalApproval` banner renders below the message
- [ ] Banner shows the proposed command with Run / Dismiss buttons
- [ ] Clicking Run sends the command string to the IPC handler `chat:write-terminal`
- [ ] IPC handler writes `command + "\n"` to the active node-pty tab
- [ ] Clicking Dismiss removes the banner; command is not written

**Delivered by:** Phase 8–9 → Conversation 3

---

### Story S3.2: Terminal write approval is configurable
**As a** Pathly Studio user, **I want** to toggle between manual approval and auto-execute for AI commands, **so that** I can choose my comfort level.

**Acceptance Criteria:**
- [ ] Settings store has `chatAutoApprove: boolean` (default: `false`)
- [ ] When `chatAutoApprove` is `true`, commands execute immediately without banner
- [ ] A toggle in the ChatPanel header shows current mode (Manual / Auto)
- [ ] Setting persists in Zustand persist middleware (survives app restart)

**Delivered by:** Phase 9 → Conversation 3

---

### Story S4.1: PageAnalyzer reads current Studio screen and adds to context
**As a** Pathly Studio user, **I want** the AI to see what's on my screen right now, **so that** it can give specific advice about the buttons and state I'm looking at.

**Acceptance Criteria:**
- [ ] `analyzePageDirect()` runs in Studio's renderer before each message send
- [ ] Result (buttons, forms, text blocks visible on screen) is appended to the message payload
- [ ] Python chat server injects screen elements into the system prompt under `## Current Screen`
- [ ] Screen context adds no more than 500 tokens to the prompt

**Delivered by:** Phase 10–12 → Conversation 4

---

### Story S4.2: Skills list is always in the system prompt
**As a** Pathly Studio user, **I want** the AI to know what Pathly slash commands exist, **so that** it can tell me exactly what to type.

**Acceptance Criteria:**
- [ ] System prompt includes a `## Available Skills` section listing all `/pathly` skill names
- [ ] Skills list is read from the Pathly skills manifest at startup
- [ ] AI references skill names correctly in responses (e.g. `/pathly build`, `/pathly review`)

**Delivered by:** Phase 11 → Conversation 4
