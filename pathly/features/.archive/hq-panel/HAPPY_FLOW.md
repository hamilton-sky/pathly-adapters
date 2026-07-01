---
name: Happy Flow
---
# HQ Panel — Happy Flow

## Overview

A developer opens Pathly Studio after the `multi-adapter-runner` backend is running. They load a feature project, switch to the HQ panel, and kick off an autonomous pipeline run. The HQ panel shows them the active stage and adapter in real time, presents a decision menu when the runner needs human confirmation, and lets them confirm the choice — all from within the panel without touching a terminal or external tool.

---

## Step-by-Step Happy Flow

### Step 1: Open Studio and navigate to HQ

- **User does:** Launches Electron Studio; opens a feature project; clicks the "HQ" tab.
- **System does:** HQ panel mounts; `useHQ.ts` opens an `EventSource` to `http://127.0.0.1:8765/events/runner`. `runnerStore` is in initial state: `status = 'idle'`, all other fields null/zero.
- **State after:** `StageStatusStrip` shows a neutral placeholder. `FlowControlBar` shows Start enabled; all other buttons disabled with `opacity: 0.45`.

### Step 2: Start the run

- **User does:** Clicks the "Start" button in `FlowControlBar`.
- **System does:** `FlowControlBar` POSTs to `http://127.0.0.1:8765/runner/start`. Backend responds 200 OK. `runnerStore.status` remains `'idle'` until the first SSE event arrives (no optimistic update).
- **State after:** Start button disabled (POST in-flight, then `status` transitions to `'running'` on first SSE event).

### Step 3: Pipeline runs — stage and adapter update live

- **User does:** Observes the HQ panel.
- **System does:** SSE stream emits `STAGE_CHANGE` events. Each event: `setRunnerState({ stage: 'BUILDING', adapter: 'codex', status: 'running' })`. `StageStatusStrip` re-renders: status dot pulses, stage label reads "BUILDING", codex chip shows in `var(--green)`.
- **State after:** `FlowControlBar` shows Pause and Abort enabled. Start, Resume, Advance, Reroute, Retry are disabled.

### Step 4: Cost ticks up

- **User does:** Continues observing.
- **System does:** SSE emits `COST_UPDATE` events; `useHQ.ts` throttles store writes to one per 200 ms. `StageStatusStrip` shows running cost, e.g. "$0.014".
- **State after:** Cost display increments smoothly. Session indicator shows "Continued" if a `SESSION` event with `sessionKind: 'continued'` has been received.

### Step 5: Runner pauses for a decision

- **User does:** Observes `PathlyMenuCard` area change.
- **System does:** SSE emits `DECISION_MENU` with items `[{ id: 'approve', label: 'Approve and continue' }, { id: 'revise', label: 'Revise the plan' }]`. `runnerStore.decisionMenu` is set; `runnerStore.status = 'blocked'`. `PathlyMenuCard` switches to decision mode: items appear token-by-token via typewriter reveal with `aria-live="polite"`. `FlowControlBar` shows Advance, Reroute, Retry enabled; Pause disabled.
- **State after:** Two decision buttons are fully rendered and clickable.

### Step 6: User confirms a decision

- **User does:** Clicks "Approve and continue".
- **System does:** Button is disabled immediately (prevents double-click). POST `{ choice: 'approve' }` to `http://127.0.0.1:8765/runner/decision`. Backend responds 200 OK. `runnerStore.decisionMenu` is cleared. `PathlyMenuCard` reverts to idle/FSM-menu state.
- **State after:** Pipeline resumes; next `STAGE_CHANGE` SSE event updates the strip again.

### Step 7: Run completes

- **User does:** Observes the strip.
- **System does:** SSE emits `RUNNER_STATUS` with `status: 'idle'` (or terminal status). `runnerStore.status = 'idle'`. `StageStatusStrip` dot stops pulsing; cost shows final value.
- **State after:** `FlowControlBar` shows Start enabled; all other buttons disabled. Panel is ready for the next run.

---

## End State

The pipeline run completed with human confirmation mid-run. The developer never left the HQ panel, never typed a terminal command, and had full visibility into stage progression, cost, and adapter assignment throughout the run.

## Success Indicators

- [ ] FlowControlBar button states correctly reflect every `RunnerStatus` transition.
- [ ] `StageStatusStrip` stage and adapter chip update within one SSE event of the actual backend state change.
- [ ] `PathlyMenuCard` decision mode renders and the POST round-trip completes with a 200 response.
- [ ] Cost display shows a non-zero value after at least one `COST_UPDATE` event.
- [ ] Session indicator matches the most recent `SESSION` SSE event's `sessionKind`.
- [ ] Typecheck passes throughout the entire flow at zero errors.
