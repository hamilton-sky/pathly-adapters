---
name: Edge Cases
---

# Comms Board — Studio CommsPanel (Phase 2) — Edge Cases

## Category 1: Server / network

### EC-1.1: FSM server down
- **Trigger:** the human opens the panel while `pathly-fsm-http` isn't running
- **Expected behavior:** `commsApi.getMessages` resolves to `[]`; `postMessage` returns `{ok:false}`; the panel shows an empty/offline state; Studio does not crash or throw to render
- **Handled in:** Phase 2 (commsApi `.catch`) + Phase 6 (empty state)

### EC-1.2: SSE connection drops mid-session
- **Trigger:** the server restarts or the connection is interrupted
- **Expected behavior:** `EventSource` auto-reconnects; on reconnect the effect re-runs `getMessages` to reconcile anything missed; no duplicate cards (dedup by id)
- **Handled in:** Phase 3 (effect cleanup + initial load on (re)subscribe)

### EC-1.3: Optimistic post fails
- **Trigger:** the human sends a message but the POST fails
- **Expected behavior:** the optimistic message is marked failed with a retry affordance; it is never silently dropped
- **Handled in:** Phase 8

## Category 2: Data / dedup

### EC-2.1: Duplicate COMMS_UPDATE for a known id
- **Trigger:** the SSE echo arrives for a message already shown optimistically
- **Expected behavior:** `appendMessage` dedups by `id`; the optimistic copy is replaced/kept once, not duplicated
- **Handled in:** Phase 1

### EC-2.2: Message with empty/whitespace text
- **Trigger:** a malformed or empty message arrives
- **Expected behavior:** it is not sendable from the compose bar (button disabled); if received, it renders defensively (no crash)
- **Handled in:** Phases 1, 8

## Category 3: Scope / board

### EC-3.1: Active feature changes while viewing
- **Trigger:** the human switches features mid-view
- **Expected behavior:** the old EventSource closes; the new feature's board loads and a new subscription opens to its scope
- **Handled in:** Phase 3

### EC-3.2: Empty project/global board
- **Trigger:** toggling to Project or Global with no messages there
- **Expected behavior:** a per-board empty state, not a blank box; the feature SSE subscription is unaffected
- **Handled in:** Phases 5, 7

## Category 4: UI rules / a11y

### EC-4.1: Very long thread
- **Trigger:** dozens of messages
- **Expected behavior:** the list scrolls; pinned decisions remain visible at the top
- **Handled in:** Phase 5

### EC-4.2: Component exceeds the size cap
- **Trigger:** `CommsMsgCard` accumulates variants (warning ack, escalation banner)
- **Expected behavior:** extract the banner/ack into a sub-component so each file stays under ~150 lines (Studio rule)
- **Handled in:** Phase 10

## Known Limitations
- **Single feature panel** — no simultaneous multi-feature view; that is the Phase 4 command center.
- **No artifact attach** — the compose bar omits Attach; `/comms/attach` is a 501 stub until a later phase.
- **Project/Global are read + post, not live** — Phase 2 subscribes SSE to the feature scope only; project/global refresh on toggle, not push. Live multi-scope is Phase 4.
