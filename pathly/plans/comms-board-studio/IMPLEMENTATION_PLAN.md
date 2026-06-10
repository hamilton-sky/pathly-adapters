---
name: Implementation Plan
---
# Comms Board — Studio CommsPanel (Phase 2) — Implementation Plan

## Overview

Build the Studio CommsPanel: a Zustand store + a `fetch` service over the Phase 1 `/comms/*`
API, a second SSE subscription for live updates, and a docked HQ panel that displays the
board, lets the human post, answers questions, and surfaces decisions/warnings/escalations.
Single-feature scope; the 3-panel command center is Phase 4.

## Layer Architecture

```
FSM HTTP (Phase 1)        Studio service          Studio state         Studio UI
/comms/*  + /events/comms → services/commsApi.ts → store/commsStore → components/HQ/CommsPanel
                            (fetch wrappers)        (Zustand)           (React, CSS modules)
                                  ▲ SSE COMMS_UPDATE handled in useHQ.tsx ─────────┘
```

## Phases

### Phase 1: commsStore   ← Conversation: 1
**File:** `studio/src/renderer/src/store/commsStore.ts` — CREATE
**Done when:** `useCommsStore.getState().appendMessage(m)` adds a message and dedups by id; typecheck passes.
**Delivers stories:** S1.1
**Depends on:** nothing
**Enables:** all UI phases
**Details:** `interface CommsMessage { id; board; scope; from_agent; to_agent; type; text; options?; status; ts; ... }`. State: `messages`, `board:'feature'|'project'|'global'`, `scope`, `pendingCount`, `loading`. Actions: `appendMessage` (dedup by id, recompute pendingCount), `setMessages`, `markRead`, `setBoard`, `clear`. Mirror `store/chatStore.ts` `create<...>()` shape.
**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

### Phase 2: commsApi service   ← Conversation: 1
**File:** `studio/src/renderer/src/services/commsApi.ts` — CREATE
**Done when:** each function issues the right `fetch` to `127.0.0.1:8765` and resolves without throwing on network error.
**Delivers stories:** S1.1
**Depends on:** Phase 1 (types)
**Enables:** Phases 8–10
**Details:** `postMessage({feature, board?, scope?, type, text, options?})`, `getMessages({feature, board?, scope?})`, `searchMessages({query, feature, board?, k?})`, `answerQuestion({question_id, answer, option_id?})`, `acknowledgeMessage({message_id, agent})`. Use the raw `fetch('http://127.0.0.1:8765/comms/...', {method, headers:{'Content-Type':'application/json'}, body})` pattern from `useHQ.tsx handleAgentAnswer`. Map the selected board → params: feature→`scope=feature`, project→`scope=projectRoot`, global→`scope='global'`. All errors `.catch` → return `{ok:false}`.
**Verify:** typecheck

### Phase 3: SSE + initial load wiring   ← Conversation: 1
**File:** `studio/src/renderer/src/components/HQ/useHQ.tsx` — MODIFY; `store/notificationStore.ts` — MODIFY; `store/index.ts` — MODIFY
**Done when:** posting a message to the active feature (via curl) makes it appear in `commsStore` without a manual refresh.
**Delivers stories:** S1.2
**Depends on:** Phases 1–2
**Enables:** Phase 4+
**Details:** Add a `useEffect` keyed on `activeTopic` that (a) calls `commsApi.getMessages` → `setMessages`, (b) opens `new EventSource('http://127.0.0.1:8765/events/comms?scope=' + encodeURIComponent(activeTopic))`, (c) on a `COMMS_UPDATE` event appends/fetches the message into `commsStore`, (d) returns a cleanup that closes the EventSource. Mirror the existing `/events/runner` effect (lines ~219–379). Add `'comms_update'` to `NotifCategory` + `DEFAULT_CATEGORIES` in `notificationStore.ts`. Re-export `useCommsStore` from `store/index.ts`.
**Verify:** typecheck; manual: `curl POST /comms/post {feature:<active>}` → message appears in the store (devtools)

---

### Phase 4: CommsMsgCard   ← Conversation: 2
**File:** `studio/src/renderer/src/components/HQ/CommsPanel/CommsMsgCard.tsx` (+ `.module.css`) — CREATE
**Done when:** a message renders with author/type/text and a `data-type` visual variant; decisions show a 📌.
**Delivers stories:** S2.1
**Depends on:** Phase 1
**Enables:** Phase 5
**Details:** Props `{ msg: CommsMessage }`. Root element carries `data-type={msg.type}`. CSS module styles each variant (status muted, decision green + pin, warning orange border, discovery cyan, answer indented). No inline styles. Keep < 150 lines.
**Verify:** typecheck

### Phase 5: CommsMsgList   ← Conversation: 2
**File:** `studio/src/renderer/src/components/HQ/CommsPanel/CommsMsgList.tsx` (+ `.module.css`) — CREATE
**Done when:** the list renders decisions pinned at top, then the rest newest-first; scrolls when long.
**Delivers stories:** S2.1
**Depends on:** Phase 4
**Enables:** Phase 6
**Details:** Props `{ messages: CommsMessage[] }`. Partition into pinned `decision`s and the rest; render `CommsMsgCard` for each. Empty-state element when `messages.length === 0`.
**Verify:** typecheck

### Phase 6: CommsPanel shell + mount   ← Conversation: 2
**File:** `studio/src/renderer/src/components/HQ/CommsPanel/CommsPanel.tsx` (+ `.module.css`) + `hooks/useCommsPanel.ts` — CREATE; `components/HQ/index.tsx` — MODIFY
**Done when:** the panel appears docked in the HQ for an active feature and shows live messages.
**Delivers stories:** S2.1
**Depends on:** Phases 3, 5
**Enables:** Phases 7–10
**Details:** `CommsPanel` = header (title + subtitle "Agents read this at the start of each stage") + `BoardToggle` slot + `CommsMsgList` + a send-bar slot (filled in Conv 3). `useCommsPanel.ts` holds UI state (active board, derived filtered messages from `commsStore`). Mount `<CommsPanel />` in `HQ/index.tsx` after `<AgentQuestionCard>` (~line 39), shown when an active topic exists.
**Verify:** typecheck; manual: panel visible, shows messages

### Phase 7: BoardToggle (pill toggles)   ← Conversation: 2
**File:** `studio/src/renderer/src/components/HQ/CommsPanel/BoardToggle.tsx` (+ `.module.css`) — CREATE
**Done when:** clicking Feature/Project/Global loads that board and highlights the active pill.
**Delivers stories:** S2.2
**Depends on:** Phase 6
**Enables:** —
**Details:** **Pill/chip toggles, not tabs** (CONSULTATION §3.2). Props `{ board, onSelect }`. Active pill via `data-active`. On select, `useCommsPanel` calls `commsApi.getMessages` with the mapped board/scope and `setMessages` + `setBoard`. Buttons `type="button"`, `aria-pressed` per pill.
**Verify:** typecheck; manual: toggling switches the visible board

---

### Phase 8: CommsInput (compose)   ← Conversation: 3
**File:** `studio/src/renderer/src/components/HQ/CommsPanel/CommsInput.tsx` (+ `.module.css`) — CREATE; fill the send slot in `CommsPanel.tsx`
**Done when:** typing text + Send posts to the current board and the message appears.
**Delivers stories:** S3.1
**Depends on:** Phases 2, 6
**Enables:** —
**Details:** Textarea + a type selector that **defaults to "Note"**, changed after writing (designer §3.4): Decision / Task / Note / Question. Send → `commsApi.postMessage({feature, board, type, text, from:'human'})`, optimistic append (reconciled by SSE echo, dedup by id). Send disabled on empty text. `type="button"`.
**Verify:** typecheck; manual: post a Note → appears

### Phase 9: CommsQuestionCard   ← Conversation: 3
**File:** `studio/src/renderer/src/components/HQ/CommsPanel/CommsQuestionCard.tsx` (+ `.module.css`) — CREATE; wire into `CommsMsgCard`/list for `type==='question'`
**Done when:** an agent question renders options; clicking one answers it.
**Delivers stories:** S3.2
**Depends on:** Phases 2, 4
**Enables:** —
**Details:** Reuse `AgentQuestionCard` structure: props `{ msg }`, render `msg.options` as `type="button"` option buttons; on click → `commsApi.answerQuestion({question_id: msg.id, answer, option_id})`; show "answered" until the SSE update marks status resolved.
**Verify:** typecheck; manual: post a question via curl → answer from UI → resolves

### Phase 10: Warnings / acknowledge / escalation banner   ← Conversation: 3
**File:** `studio/src/renderer/src/components/HQ/CommsPanel/CommsMsgCard.tsx` (+ `.module.css`) — MODIFY
**Done when:** warnings show an Acknowledge action; escalations render a distinct red banner.
**Delivers stories:** S3.2
**Depends on:** Phases 4, 2
**Enables:** —
**Details:** For `type==='warning'`: an "Acknowledge" button → `commsApi.acknowledgeMessage`. For `type==='escalation'`: a red banner variant (`data-type='escalation'`) styled in the module to stand out. Keep `CommsMsgCard` under 150 lines — extract the banner to a sub-component if needed.
**Verify:** typecheck; manual: escalation shows red banner; acknowledge a warning

## Prerequisites
- Phase 1 backend running (`pathly-fsm-http`) for manual verification
- Node deps installed (`npm i` in studio); Studio builds today

## Key Decisions
- **Single feature panel, not the command center** — Phase 2 ships the one-feature CommsPanel; the resizable 3-panel command center is Phase 4 (SPEC §19).
- **Pill toggles, not tabs** — multi-state board selector reads as a filter, not mutually-exclusive tabs (CONSULTATION §3.2).
- **Type-after-write compose** — default "Note", refine the type only when meaning something specific (CONSULTATION §3.4).
- **Reuse `AgentQuestionCard`** — comms questions mirror the existing agent-question UI rather than a new pattern.
- **`board`/`scope` per SPEC** — UI maps the board toggle to `board` ∈ {feature,project,global} + the right `scope` identifier; never reintroduce the inverted convention.
- **Errors non-blocking** — `commsApi` swallows network errors and returns flags; the FSM server may be down without crashing Studio.
