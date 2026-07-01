# studio-monitor-live — Edge Cases

## Category 1: Data Race / Timing

### EC-1.1: EVENTS.jsonl initial load overwrites live SSE events
- **Trigger**: `readFile(EVENTS.jsonl)` promise resolves *after* SSE has already appended live events via `setEvents([...eventsRef.current, event])`, overwriting them.
- **Current behavior**: Live events disappear; trace resets to the file state.
- **Expected behavior**: Trace does not crash or lose data; eventual consistency is acceptable.
- **Handled in**: Phase 2 — sort `VisitRow[]` by `ts` before rendering. Do NOT fix the race itself (pre-existing bug; out of scope).

### EC-1.2: AGENT_SPAWNED arrives before its STATE_TRANSITION in SSE stream
- **Trigger**: Wall-clock ordering of SSE events is not guaranteed.
- **Current behavior**: Agent column shows the *previous* state's agent for one render frame.
- **Expected behavior**: Eventual consistency — agent column updates on the next event. One stale frame is acceptable.
- **Handled in**: Phase 2 — documented as intentional; no fix required.

### EC-1.3: `formatRelativeTime` computed at render time, not event time
- **Trigger**: A cached component does not re-render; old events show "now" indefinitely.
- **Current behavior**: Relative time is stale if the component doesn't re-render.
- **Expected behavior**: Timestamps auto-refresh every 30 seconds regardless of new events.
- **Handled in**: Phase 2 — `useInterval` 30s tick forces re-render of the trace; relative times stay fresh.

---

## Category 2: State / Data Availability

### EC-2.1: `monitorSource` is null on initial mount
- **Trigger**: Project loads but SSE hasn't connected and chokidar hasn't started.
- **Current behavior**: Would show `○ polling` (incorrect — nothing is polling yet).
- **Expected behavior**: Show `—` (neutral).
- **Handled in**: Phase 3 — three-state badge: `'sse'` → `● live`, `'chokidar'` → `○ polling`, `null` → `—`.

### EC-2.2: `pipelineStates` is empty on first render
- **Trigger**: Flow YAML hasn't been read yet or the YAML has no `states:` block.
- **Current behavior**: FsmView falls back to default `['STORMING','PLANNING','BUILDING','REVIEWING','DONE']`.
- **Expected behavior**: Fallback renders; rail dot still works.
- **Handled in**: Phase 1 — existing fallback array is correct; no change needed.

### EC-2.3: Custom/unknown flow name (`fsmState.flow` not 'team'/'debug'/'explore')
- **Trigger**: User creates a custom flow (e.g., `my-pipeline.flow.yaml`).
- **Current behavior**: Plan conditions on exact string `'debug' || 'explore'`. Unknown names default to `conv N`.
- **Expected behavior**: `conv N` fallback for all unknown flow names — correct behavior, but must be documented so the builder doesn't try to infer loop behavior from flow name.
- **Handled in**: Phase 1 — note in implementation: "custom flow names → `conv N`; loop detection is topology-based, not name-based."

### EC-2.4: `fsmState.current` is 'DONE' or 'IDLE' when Monitor opens
- **Trigger**: User opens Monitor for a completed or inactive topic.
- **Current behavior**: FsmView shows no active dot; EventLog shows full history.
- **Expected behavior**: Rail shows all states as completed (or all as pending); no pulsing. Banner does not appear. Correct behavior — no change needed.
- **Handled in**: Phase 1 (rail) and Phase 5 (banner) — `isRunning` guard handles this.

### EC-2.5: Last-used flow file deleted between sessions
- **Trigger**: User deletes a `.flow.yaml` file, then reopens Studio.
- **Current behavior**: `readFile` would throw; canvas shows broken state.
- **Expected behavior**: Catch the error, clear `lastUsedFlowPath` from localStorage, show empty canvas hint.
- **Handled in**: Phase 7 — explicit `catch` block clears the stored path.

### EC-2.6: `conversation` field absent from EVENTS.jsonl AGENT_DONE entries
- **Trigger**: Older FSM versions or non-standard flows may not populate `conversation` on events.
- **Current behavior**: Cost aggregation in PlanBoard would silently produce `0` or `NaN`.
- **Expected behavior**: Cost row is hidden entirely if no AGENT_DONE event has a `conversation` field.
- **Handled in**: Phase 6 — builder must check one real EVENTS.jsonl file before implementing cost filter. If field is absent, omit cost row.

---

## Category 3: UI / Interaction

### EC-3.1: Banner auto-dismiss while user is reading it
- **Trigger**: Banner appears; user moves mouse over it to read; 8s timer fires.
- **Current behavior**: Banner dismisses under the user's cursor.
- **Expected behavior**: Timer pauses on `mouseenter`, resumes on `mouseleave`.
- **Handled in**: Phase 5 — hover-to-pause via `clearTimer`/`startTimer` on `onMouseEnter`/`onMouseLeave`.

### EC-3.2: Banner reappears on new run after dismissal
- **Trigger**: User dismisses banner; pipeline finishes (DONE); then starts a new run.
- **Current behavior**: `dismissed` stays `true`; banner never shows for the new run.
- **Expected behavior**: `dismissed` resets when `isRunning` transitions `false → true`.
- **Handled in**: Phase 5 — `prevRunningRef` tracks the transition and calls `setDismissed(false)`.

### EC-3.3: Multiple flows active when Studio opens
- **Trigger**: Two CLI sessions started the FSM before Studio was opened.
- **Current behavior**: Banner would show for "most recently active" — but `activeFlowSessions` isn't populated from CLI; it's populated from Studio's own Monitor useEffect.
- **Expected behavior**: Banner does not appear for CLI-originated sessions (they don't populate `activeFlowSessions`). Monitor shows topic from `activeTopic`.
- **Handled in**: Phase 4 — `activeFlowSessions` only populated by Studio-launched sessions. CLI discovery is Post-MVP.

### EC-3.4: Pulsing border layout shift if border-width changes
- **Trigger**: If `border-left-width` animates between `0` and `3px`.
- **Current behavior**: Layout shift on every pulse cycle.
- **Expected behavior**: Card always has `3px` border-left; only the **color** changes.
- **Handled in**: Phase 6 — pulse keyframe animates `border-left-color` only; `border-left-width: 3px` is always present.

### EC-3.5: Tab bar keyboard focus trap
- **Trigger**: User tabs into the tab list and presses `Tab` expecting to exit.
- **Current behavior**: Without proper ARIA tab pattern, Tab key might cycle through all tabs instead of exiting.
- **Expected behavior**: `Tab` key exits the tablist (standard ARIA pattern: Tab enters/exits; Arrow keys navigate within).
- **Handled in**: Phase 4 — `role="tablist"` + `role="tab"` + `tabIndex={isActive ? 0 : -1}` on each tab. Only the active tab is in the Tab sequence.

### EC-3.6: `prefers-reduced-motion` on pulsing animations
- **Trigger**: User has system-level reduced motion enabled.
- **Current behavior**: All pulse animations play regardless.
- **Expected behavior**: `pathly-pulse`, `pathly-pulse-border`, and the rail dot CSS transition are all disabled.
- **Handled in**: Phase 1 (pulse + transition), Phase 6 (border pulse) — `@media (prefers-reduced-motion: reduce)` block in each CSS injection.

---

## Category 4: Multi-Flow

### EC-4.1: Tab bar shows for 1 active session vs 0
- **Trigger**: Exactly 1 session in `activeFlowSessions`.
- **Current behavior**: Plan spec says `>= 2` to show tab bar. Single session uses existing `activeTopic` path.
- **Expected behavior**: No tab bar for 1 session — existing header + monitor content unchanged.
- **Handled in**: Phase 4 — `Object.keys(activeFlowSessions).length >= 2` guard.

### EC-4.2: Active session ends while being viewed in tab
- **Trigger**: A pipeline finishes (DONE) while the user is viewing it in the Monitor tab.
- **Current behavior**: Session removed from `activeFlowSessions` on useEffect cleanup → tab disappears → Monitor switches to remaining session.
- **Expected behavior**: Graceful fallback to next active session or `activeTopic`.
- **Handled in**: Phase 4 — on session removal, `setActiveMonitorTab(null)` reverts to `activeTopic` path.

### EC-4.3: `activeMonitorTab` points to a session that no longer exists
- **Trigger**: Session ends between render cycles; `activeMonitorTab` still holds the old key.
- **Current behavior**: `effectiveTopic = activeMonitorTab ?? activeTopic` would use a stale key.
- **Expected behavior**: If `activeFlowSessions[activeMonitorTab]` is undefined, fall back to `activeTopic`.
- **Handled in**: Phase 4 — derive `effectiveTopic = (activeMonitorTab && activeFlowSessions[activeMonitorTab]) ? activeMonitorTab : activeTopic`.

---

---

## Category 5: SSE and Infrastructure

### EC-5.1: `EventSource.onerror` fires for both transient and fatal errors
- **Trigger**: Network hiccup (recoverable) vs. server closed connection (fatal) both trigger `onerror`.
- **Current behavior**: Both scenarios would incorrectly set `monitorSource = null` and show `—`.
- **Expected behavior**: Transient errors (`readyState === CONNECTING`) leave the badge as-is; browser is auto-reconnecting. Only `readyState === CLOSED` (fatal) sets `monitorSource = null`.
- **Handled in**: Phase 3 — `onerror` handler branches on `es.readyState`.

### EC-5.2: localStorage throws in sandboxed context
- **Trigger**: Electron `BrowserWindow` with strict sandboxing, or storage quota exceeded, or corrupted user profile.
- **Current behavior**: Unguarded `localStorage.getItem/setItem` throws; app crashes on mount.
- **Expected behavior**: Silently fall back to empty state; canvas shows empty hint.
- **Handled in**: Phase 4 — all localStorage reads/writes wrapped in `try/catch`.

### EC-5.3: `fsmState.waitingFor` never clears (perpetual blocked state)
- **Trigger**: FSM emits a `waitingFor` value but the artifact never arrives and the flow is not running.
- **Current behavior**: Amber banner would show indefinitely even after the flow ends.
- **Expected behavior**: Amber banner hidden when `fsmState.current === 'DONE'` or `'IDLE'`, regardless of `waitingFor` value.
- **Handled in**: Phase 7 — banner condition: `isBlocked && isRunning` (not just `isBlocked`).

### EC-5.4: CSP blocks runtime `<style>` injection for `@keyframes`
- **Trigger**: Electron `BrowserWindow` has a strict Content Security Policy with `style-src` not including `'unsafe-inline'`.
- **Current behavior**: `document.createElement('style')` injection for `pathly-pulse` and `pathly-pulse-border` keyframes is silently blocked; animations never fire.
- **Expected behavior**: Animations fail silently (base state is no animation anyway — opt-in pattern means no visual regression). No console errors.
- **Handled in**: Phase 1/6 — the opt-in motion pattern means failure = no motion = acceptable. But: confirm CSP allows `'unsafe-inline'` for style, or move keyframes to a static CSS file if blocked.

---

## Known Limitations

- **CLI session discovery is Post-MVP.** Sessions started from the terminal are not detected.
- **`isPaused` is always `false`.** The `◐` half-filled tab indicator is deferred — no production signal sets `isPaused: true`.
- **Monitor tabs (S4) deferred.** Not implemented until production data shows concurrent-flow usage.
- **Stop/cancel and error drill-down absent.** Real product gaps; planned for follow-on feature after Conv 2 ships.
- **EVENTS.jsonl / SSE race is pre-existing.** The initial file load can overwrite live events. Fixing it requires a merge strategy that is out of scope.
- **Failure detection is heuristic.** The "backward transition = failed" rule works for standard team flows but may produce false positives on custom flows with intentional backward edges.
