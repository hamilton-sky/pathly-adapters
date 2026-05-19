# Studio AI Chat — Happy Flow

## Overview

A developer opens Pathly Studio mid-pipeline, unsure what to do next. They open the AI chat sidebar, ask a simple question, get a specific answer that references their current stage and plan, and the AI offers to run the next command. The developer approves with one click and the command executes in the terminal — no copy-pasting, no documentation lookup.

---

## Step-by-Step Happy Flow

### Step 1: User opens Studio with an active feature
- **User does:** Launches Pathly Studio with a feature in the `plan_complete` FSM stage
- **System does:** Studio loads, ChatPanel is visible on the right (320px wide)
- **State after:** FSM server running on :8765, chatStore initialized with empty messages

### Step 2: User opens the chat panel
- **User does:** Clicks the ChevronLeft toggle (panel is open by default)
- **System does:** Panel is already open; user sees empty message list and input bar
- **State after:** ChatPanel expanded, input focused

### Step 3: User asks what to do next
- **User does:** Types "what should I do next?" and presses Enter
- **System does:**
  1. ChatPanel calls `buildPathlyContext()` — fetches FSM stage (`plan_complete`), runs PageAnalyzer, gathers skills list
  2. POSTs to `http://127.0.0.1:8765/chat` with message + context
  3. ChatAgent builds system prompt: stage = plan_complete, feature name, plan summary, screen elements showing [Build] button, skills list
  4. Ollama (phi4-mini) streams response
- **State after:** User message appears in list, streaming indicator visible

### Step 4: AI streams a specific, actionable answer
- **User does:** Reads the response
- **System does:** Streams: *"Your plan is complete. The next step is to build. I can see the Build button on your screen. Run `/pathly build` to start."* — then a fenced code block: ` ```\n$/pathly build\n``` `
- **State after:** Message fully rendered; TerminalApproval banner appears below the message

### Step 5: User approves the command
- **User does:** Clicks Run in the approval banner
- **System does:** Calls `window.electronAPI.writeToTerminal('/pathly build')` → IPC → `activePtys.get(activeTabId).write('/pathly build\n')`
- **State after:** Terminal shows `/pathly build` executing; pipeline advances to build stage

### Step 6: User continues the conversation
- **User does:** Asks "what's happening now?" while build runs
- **System does:** Context is re-fetched (stage now `build_in_progress`), AI responds with build-specific guidance
- **State after:** User is guided through the full pipeline without leaving Studio

---

## End State

The user completes a full Pathly pipeline cycle — plan → build → review → test — guided entirely by the AI chat without needing to remember any commands or read the documentation.

## Success Indicators
- [ ] AI response correctly identifies the FSM stage in every message
- [ ] Approval banner appears for every command in AI responses
- [ ] Command executes in terminal within 200ms of clicking Run
- [ ] Chat history persists across panel toggle (collapse/expand)
- [ ] Streaming is smooth — no visible jank or layout shift
