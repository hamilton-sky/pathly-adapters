---
name: User Stories
---
# Comms Board — Studio CommsPanel (Phase 2) — User Stories

## Context

Phase 1 put the communication board on the backend — a human can steer agents by posting
to the board via curl, and agents read it at `/next_action`. But there is no UI: you can't
see what agents posted, answer their questions, or pin a decision without the command line.

Phase 2 builds the **CommsPanel** in Studio: a single-feature visual board docked in the HQ.
It shows the active feature's board in real time over SSE, lets the human post messages and
answer questions, pins decisions, and surfaces warnings/escalations. It reads the active
feature from runner state and talks to the Phase 1 `/comms/*` endpoints.

---

## Stories

### Story 1.1: Comms store + API client
**As a** Studio developer, **I want** a `commsStore` and a `commsApi` service, **so that**
the UI has one source of truth for board messages and one place to call the FSM `/comms/*` endpoints.

**Acceptance Criteria:**
- [ ] `commsStore.ts` exposes `messages: CommsMessage[]`, `board: 'feature'|'project'|'global'`, `scope: string`, `pendingCount: number`, and actions `appendMessage`, `setMessages`, `markRead`, `setBoard`, `clear`
- [ ] `commsApi.ts` exposes `postMessage`, `getMessages`, `searchMessages`, `answerQuestion`, `acknowledgeMessage` as `fetch` wrappers to `http://127.0.0.1:8765/comms/*`
- [ ] API errors are non-blocking (caught; surfaced via a returned error, never throw to render)
- [ ] `useCommsStore` is re-exported from `store/index.ts`
- [ ] `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` passes

**Edge Cases:**
- Server down → `getMessages` resolves to `[]`, `postMessage` returns an error flag, no crash
- Duplicate `COMMS_UPDATE` for an already-present id → `appendMessage` dedups by id

**Delivered by:** Phase 1–2 → Conversation 1

---

### Story 1.2: Live board updates over SSE
**As a** human, **I want** the panel to update in real time when a message is posted,
**so that** I see agent status and questions the moment they happen.

**Acceptance Criteria:**
- [ ] `useHQ.tsx` opens a second `EventSource` to `/events/comms?scope=<activeTopic>` in its own effect
- [ ] On `COMMS_UPDATE`, it fetches/appends the new message into `commsStore`
- [ ] When the active feature (topic) changes, the panel loads that feature's messages via `getMessages` and re-subscribes to the new scope
- [ ] The EventSource is closed and recreated cleanly on topic change / unmount (no leak)
- [ ] A `'comms_update'` category is added to `notificationStore`; a toast fires for new agent messages (respecting the category's enabled flag)

**Edge Cases:**
- SSE drops → browser auto-reconnects (EventSource default); on reconnect, a fresh `getMessages` reconciles missed messages
- No active topic → no subscription, panel shows an empty/idle state

**Delivered by:** Phase 3 → Conversation 1

---

### Story 2.1: See the board — message thread
**As a** human, **I want** to see the feature's board as a readable thread, **so that** I
understand what was decided and what agents are doing.

**Acceptance Criteria:**
- [ ] `CommsPanel` is docked in the HQ (after `AgentQuestionCard`) and shows when there is an active topic
- [ ] Messages render newest-relevant, with `decision` messages **pinned at the top** with a 📌 marker
- [ ] Each message shows author, type, and text; type drives a `data-type` visual variant (status/decision/nudge/warning/discovery/answer/question)
- [ ] The panel header carries the mental-model subtitle: *"Agents read this at the start of each stage"*
- [ ] No inline styles; all variants handled in `.module.css` via `data-type`

**Edge Cases:**
- Empty board → friendly empty state, not a blank box
- Very long thread → panel scrolls; pinned decisions stay visible

**Delivered by:** Phase 4–6 → Conversation 2

---

### Story 2.2: Switch board scope
**As a** human, **I want** to switch between Feature / Project / Global views, **so that**
I can read decisions at each scope without leaving the panel.

**Acceptance Criteria:**
- [ ] A `BoardToggle` renders **pill/chip toggles** (NOT tabs — designer guidance CONSULTATION §3.2) for Feature / Project / Global
- [ ] Selecting a board loads that board's messages (`getMessages` with the right `board` + `scope`: feature→activeTopic, project→projectRoot, global→'global')
- [ ] The active pill is visually distinct via a `data-active` / `.active` state
- [ ] Switching board does not lose the SSE subscription to the feature scope

**Edge Cases:**
- Project/global board empty → empty state per board
- Toggle while a post is in flight → post targets the board selected at send time

**Delivered by:** Phase 7 → Conversation 2

---

### Story 3.1: Post to the board
**As a** human, **I want** to type a message and post it to the current board, **so that**
I can steer the next agent without the command line.

**Acceptance Criteria:**
- [ ] `CommsInput` has a textarea and a type selector that **defaults to "Note"** and is changed *after* writing (designer §3.4): Decision / Task / Note / Question (Attach deferred — backend is a 501 stub)
- [ ] Send calls `commsApi.postMessage` with the correct `board`/`scope`/`type`/`text` and `from: 'human'`
- [ ] The posted message appears optimistically and is reconciled by the SSE echo (dedup by id)
- [ ] Empty/whitespace text is not sendable (button disabled); every button has `type="button"`

**Edge Cases:**
- Post fails (server down) → the optimistic message shows a retry affordance; nothing is silently lost
- Posting a Question includes an options affordance (optional in Phase 2; plain question allowed)

**Delivered by:** Phase 8 → Conversation 3

---

### Story 3.2: Answer questions, acknowledge, see escalations
**As a** human, **I want** to answer agent questions and see warnings/escalations clearly,
**so that** the pipeline gets unblocked from the UI.

**Acceptance Criteria:**
- [ ] A `question`-type message renders a `CommsQuestionCard` (reusing the `AgentQuestionCard` pattern) with its options as buttons
- [ ] Clicking an option calls `commsApi.answerQuestion`; the card then shows "answered" and the question's status flips to resolved on the next update
- [ ] `warning` messages show an "Acknowledge" affordance calling `commsApi.acknowledgeMessage`
- [ ] `escalation` messages render a red banner variant (`data-type='escalation'`) that stands out from normal messages
- [ ] All interactive elements use ARIA labels; the answer buttons have `type="button"`

**Edge Cases:**
- Answering an already-resolved question → no-op, card reflects resolved state
- Escalation with no options → red banner with free-text reply via the compose bar

**Delivered by:** Phase 9–10 → Conversation 3
