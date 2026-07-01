---
name: Happy Flow
---
# Comms Board (Phase 1 — Backend Core) — Happy Flow

## Overview

A developer is mid-feature. The builder is about to start a stage. The human wants the
builder to focus on one file and skip another — without stopping the pipeline or editing
plan files. They post one message to the board; the next agent reads it automatically.

## Step-by-Step Happy Flow

### Step 1: Human posts a nudge mid-feature
- **User does:** `curl -X POST /comms/post -d '{"feature":"send-to-agent-diff","from":"human","type":"nudge","text":"Focus on Editor/index.tsx first. CommentsPanel is already correct."}'`
- **System does:** stores the row in `comms_messages` (status=pending), returns its id immediately, and kicks off async embedding on a daemon thread
- **State after:** the message is queryable instantly; its 384-dim vector lands in `comms_embeddings` ~200ms later

### Step 2: Embedding completes in the background
- **User does:** nothing
- **System does:** `embed_async` computes the vector with all-MiniLM-L6-v2 (model already warm from startup) and calls `store_embedding`
- **State after:** the message is now retrievable by semantic similarity, not just recency

### Step 3: The next stage starts — FSM retrieves board context
- **User does:** the runner (or a manual `pathly-fsm-call next-action`) calls `/next_action` for the feature
- **System does:** `retrieve_board_context()` reads the feature's board_scope (all-true by default), embeds the upcoming task description, queries feature(k=3)/project(k=2)/global(k=1), and unions any pending decisions/escalations
- **State after:** a `## Communication Board` markdown block is built containing the nudge

### Step 4: The agent opens with the board in its prompt
- **User does:** nothing
- **System does:** `fsm_ops.build_prompt()` appends the block after `## Pipeline History`; the full text is returned in `agent_hint.instructions`
- **State after:** the builder's prompt now contains "Focus on Editor/index.tsx first…" — it knows the human's intent before writing a line

### Step 5: (Optional) The agent reads/answers via the API
- **User does:** watches; later answers any question the agent posted
- **System does:** the agent can `POST /comms/post` a status/discovery, or `POST /comms/acknowledge`; each broadcasts a `COMMS_UPDATE` over `/events/comms`
- **State after:** a persistent, bidirectional thread exists for the feature — ready for the Studio UI in the Phase 2 plan

## End State
A human can steer any agent at any point by posting to the board, and every subsequent
agent automatically starts with the most relevant decisions and constraints — with no
Studio changes and no plan-file edits.

## Success Indicators
- [ ] A nudge posted via curl appears verbatim in the next `/next_action` `agent_hint.instructions`
- [ ] A paraphrased `/comms/search` query returns the original message in the top results
- [ ] Disabling a board via board_scope removes its messages from the injected block
- [ ] `/next_action` latency increase from retrieval is < ~150ms at expected volumes
