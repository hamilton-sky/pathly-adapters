---
name: Edge Cases
---
# HQ Panel — Edge Cases

## Category 1: Backend Not Available

### EC-1.1: `multi-adapter-runner` server not running at Phase 0
- **Trigger:** Developer starts Conv 1 before `multi-adapter-runner` has shipped or the server is not running.
- **Current behavior:** the runner start endpoint returns connection-refused when the backend is down.
- **Expected behavior:** Phase 0 pre-flight detects the failure, writes `OPEN: backend not reachable` to `pathly/plans/hq-panel/feedback/HUMAN_QUESTIONS.md`, and halts. Builder does NOT proceed to Phase 1.
- **Handled in:** Phase 0 — Conv 1

### EC-1.2: Backend drops during an active run
- **Trigger:** FSM server crashes or is killed while the SSE stream is open.
- **Current behavior:** `EventSource.onerror` fires; no recovery.
- **Expected behavior:** `useHQ.ts` catches `onerror`; sets `errorMessage: 'Reconnecting...'` in `runnerStore`; schedules a 3-second reconnect. `StageStatusStrip` shows the "Reconnecting…" message. After 3 s a new `EventSource` is created.
- **Handled in:** Phase 4 — Conv 2

### EC-1.3: POST to `/runner/*` returns non-2xx
- **Trigger:** Any control button POST fails (network error, 500, 409 conflict, etc.).
- **Current behavior:** Silent failure (no feedback to user).
- **Expected behavior:** `setRunnerState({ errorMessage: '<descriptive text>' })` is called; `StageStatusStrip` renders the error with `role="alert"`. No state transition in `runnerStore.status` occurs from this error alone.
- **Handled in:** Phase 3 — Conv 1

---

## Category 2: Race Conditions

### EC-2.1: `DECISION_MENU` arrives twice before user clicks
- **Trigger:** Runner re-emits the decision menu event (retry or duplicate delivery).
- **Current behavior:** A second render pass could append a second set of menu items.
- **Expected behavior:** `runnerStore.setDecisionMenu(items)` replaces (not appends) the existing menu. The component unmounts and remounts the typewriter animation, restarting cleanly.
- **Handled in:** Phase 5 — Conv 2

### EC-2.2: User double-clicks a decision menu item
- **Trigger:** User clicks "Approve" twice rapidly before the POST returns.
- **Current behavior:** Two POSTs sent; backend may process both.
- **Expected behavior:** On first click the button receives `disabled` immediately, preventing a second click. Only one POST is sent.
- **Handled in:** Phase 5 — Conv 2

### EC-2.3: User clicks Abort while AbortConfirmStrip is already visible
- **Trigger:** The Abort button is clicked, the strip appears; then the Abort button is activated again via keyboard before strip closes.
- **Current behavior:** Undefined.
- **Expected behavior:** If `AbortConfirmStrip` is already shown, clicking Abort again has no effect (the strip's visibility is a boolean toggle set to `true`, already true). The confirm button in the strip is the only POST path.
- **Handled in:** Phase 3 — Conv 1

---

## Category 3: SSE Data Edge Cases

### EC-3.1: Malformed SSE payload (unparseable JSON)
- **Trigger:** Backend emits a malformed event data string.
- **Current behavior:** `JSON.parse` throws; unhandled exception.
- **Expected behavior:** `useHQ.ts` wraps each `JSON.parse` in a try/catch. On parse error: log to console and call `setRunnerState({ errorMessage: 'Stream parse error' })`. Do not crash.
- **Handled in:** Phase 4 — Conv 2

### EC-3.2: `COST_UPDATE` events arrive at very high frequency (>5/s)
- **Trigger:** Backend emits cost events faster than the 200 ms throttle.
- **Current behavior:** Without throttle, React re-renders on every event.
- **Expected behavior:** The `useRef` timestamp check in `useHQ.ts` drops updates that arrive within 200 ms of the last committed write. The UI updates at most 5 times per second.
- **Handled in:** Phase 4 — Conv 2

### EC-3.3: `SESSION` event never received
- **Trigger:** Backend run starts but never emits a `SESSION` event.
- **Current behavior:** `sessionKind` remains `null`.
- **Expected behavior:** `StageStatusStrip` renders no session indicator label — the slot is simply empty. No "undefined" or "null" text is shown.
- **Handled in:** Phase 6 — Conv 2

---

## Category 4: Store / Adapter State Edge Cases

### EC-4.1: `adapter` is null in `runnerStore`
- **Trigger:** SSE has not yet emitted a `STAGE_CHANGE` event, or the backend emits one without an adapter field.
- **Current behavior:** Undefined — chip might throw on null access.
- **Expected behavior:** `StageStatusStrip` renders no adapter chip when `adapter` is null. No error thrown.
- **Handled in:** Phase 3 — Conv 1

### EC-4.2: `adapters.gen.ts` not found at Phase 0
- **Trigger:** `multi-adapter-runner` backend feature not yet delivered.
- **Current behavior:** Import would fail at compile time.
- **Expected behavior:** Phase 0 pre-flight globs for the file. If absent, writes an `OPEN:` block to `pathly/plans/hq-panel/feedback/HUMAN_QUESTIONS.md` and halts. Builder does not proceed.
- **Handled in:** Phase 0 — Conv 1

---

## Known Limitations

- **Exponential back-off not implemented:** The SSE reconnect uses a flat 3-second delay. High-frequency restart scenarios may saturate the server. Deferred to a follow-up.
- **No offline queue for control POSTs:** If a button POST fails because the server is temporarily unreachable, the action is lost. No retry queue. User must click again.
- **Typewriter reveal is CPU-bound for long decision items:** The 20 ms interval approach is not frame-rate-aware. For very long decision item strings (>200 chars), consider `requestAnimationFrame` in a follow-up.
- **`adapters.gen.ts` color chip source:** The color chip values (`var(--accent)`, `var(--green)`, `var(--yellow)`) are hardcoded in `StageStatusStrip`. If `adapters.gen.ts` defines different color tokens in the future, this component will need updating.
