---
name: Flow Diagram
---
# HQ Panel — Flow Diagram

## Happy Path: Start run → Decision → Confirm

```
User clicks "Start" in FlowControlBar
        │
        ▼
FlowControlBar
        │  POST /runner/start
        ▼
http://127.0.0.1:8765
        │  200 OK
        ▼
(no optimistic store update — wait for SSE)
        │
        ▼
EventSource /events/runner  (open in useHQ.ts)
        │
        │ STAGE_CHANGE { stage, adapter, status:'running' }
        ▼
runnerStore.setRunnerState()
        │
        ├──► StageStatusStrip re-renders
        │         dot pulses; stage label updates; adapter chip shows
        │
        └──► FlowControlBar re-renders
                  Pause + Abort enabled; Start disabled
        │
        │ COST_UPDATE { cost } (throttled 200ms)
        ▼
runnerStore.setRunnerState({ cost })
        │
        └──► StageStatusStrip cost display ticks
        │
        │ DECISION_MENU { items, status:'blocked' }
        ▼
runnerStore.setDecisionMenu(items)
runnerStore.setRunnerState({ status: 'blocked' })
        │
        ├──► PathlyMenuCard switches to decision mode
        │         typewriter reveal begins (20ms/char)
        │
        └──► FlowControlBar re-renders
                  Advance + Reroute + Retry enabled; Pause disabled
        │
User clicks a decision item in PathlyMenuCard
        │
        ▼
PathlyMenuCard
        │  button.disabled = true (immediate)
        │  POST /runner/decision { choice: item.id }
        ▼
http://127.0.0.1:8765/runner/decision
        │
        ├─ 200 OK ──► runnerStore.setDecisionMenu(null)
        │                PathlyMenuCard reverts to FSM-menu mode
        │
        └─ non-2xx ──► button.disabled = false (reverted)
                         runnerStore.setRunnerState({ errorMessage })
                         StageStatusStrip shows error (role="alert")
```

---

## Abort Flow (inline confirm)

```
User clicks "Abort" in FlowControlBar
        │
        ▼
FlowControlBar
        │  setShowAbortStrip(true)
        ▼
AbortConfirmStrip renders (role="alert")
        │
        ├─ User clicks "Confirm abort"
        │         POST /runner/abort
        │         on 200: setShowAbortStrip(false)
        │
        └─ User clicks "Cancel"
                  setShowAbortStrip(false)
                  no network call
```

---

## Reroute Flow

```
User clicks "Reroute" in FlowControlBar
        │
        ▼
ReroutePopover opens (role="dialog")
        │  shows <select> pre-filled with runnerStore.adapter
        │
        ├─ User picks adapter + clicks "Reroute"
        │         POST /runner/reroute { adapter }
        │         popover closes on 200
        │
        └─ User clicks "Cancel"
                  popover closes; no network call
```

---

## SSE Disconnect and Reconnect

```
EventSource onerror fires
        │
        ▼
useHQ.ts error handler
        │  runnerStore.setRunnerState({ errorMessage: 'Reconnecting...' })
        │  setTimeout(3000, createNewEventSource)
        ▼
StageStatusStrip renders "Reconnecting..."
        │
        │ (3 seconds pass)
        ▼
new EventSource('/events/runner') created
        │  ref updated; old source already closed
        │
        ├─ connection succeeds ──► normal event flow resumes
        │
        └─ fails again ──► onerror fires again; another 3s retry
```

---

## Component Legend

| Symbol / Name | Role in this feature |
|---|---|
| `FlowControlBar` | Issues all `/runner/*` control POSTs; owns `AbortConfirmStrip` + `ReroutePopover` visibility state |
| `AbortConfirmStrip` | Inline confirm gate for the irreversible Abort action |
| `ReroutePopover` | Adapter selection popover; POSTs `/runner/reroute` |
| `StageStatusStrip` | Reads `runnerStore` to display live stage, adapter chip, cost, session, errors |
| `PathlyMenuCard` | Dual-mode: FSM menu (original) or decision menu (when `runnerStore.decisionMenu` != null) |
| `useHQ.ts` | SSE lifecycle; dispatches all event types to `runnerStore` |
| `runnerStore` | Zustand slice — single source of truth for all runner state |
| `http://127.0.0.1:8765` | FSM + runner HTTP server (backend dependency; provided by `multi-adapter-runner`) |
