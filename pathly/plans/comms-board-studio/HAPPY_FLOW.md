---
name: Happy Flow
---
# Comms Board — Studio CommsPanel (Phase 2) — Happy Flow

## Overview

A human is running a feature in Studio. The builder agent hits an ambiguity and posts a
question to the board. The human sees it appear live in the CommsPanel, answers it with a
click, and the decision is on the board for the next agent — without touching a terminal.

## Step-by-Step Happy Flow

### Step 1: Human opens a feature
- **User does:** selects/starts a feature in the HQ
- **System does:** `useHQ` loads that feature's board (`commsApi.getMessages`) and opens an SSE subscription to `/events/comms?scope=<feature>`
- **State after:** the CommsPanel shows the feature board (pinned decisions on top), idle and listening

### Step 2: An agent posts a question
- **User does:** nothing
- **System does:** the running agent `POST /comms/post {type:'question', options:[...]}`; the FSM broadcasts `COMMS_UPDATE`; `useHQ` appends it to `commsStore`
- **State after:** a `CommsQuestionCard` renders in the panel with the options, in real time

### Step 3: Human answers from the UI
- **User does:** clicks an option on the question card
- **System does:** `commsApi.answerQuestion({question_id, answer, option_id})`; the card shows "answered"; the FSM marks the question resolved and broadcasts the update
- **State after:** the question shows resolved; the answer is on the board

### Step 4: Human pins a decision
- **User does:** types "Always use unified diff format", picks **Decision** in the compose type selector, clicks Send
- **System does:** `commsApi.postMessage({type:'decision'})`; optimistic append; SSE echo reconciles by id
- **State after:** the decision is pinned at the top of the board with 📌

### Step 5: Next agent reads it
- **User does:** lets the pipeline continue
- **System does:** the next `/next_action` injects the decision into the agent's `## Communication Board` block (Phase 1 backend)
- **State after:** the agent follows the decision — the loop the human drew from the UI is closed

## End State
The human steers agents entirely from the CommsPanel: watch status, answer questions, pin
decisions, switch board scopes — all live, no command line.

## Success Indicators
- [ ] A message posted via curl to the active feature appears in the panel within ~1s (SSE)
- [ ] Answering a question from the UI flips it to resolved
- [ ] A decision posted from the compose bar appears pinned and reaches the next agent's prompt
- [ ] Switching to Project/Global shows that scope's messages
