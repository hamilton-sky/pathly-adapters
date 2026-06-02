# visible-runner — Architecture Proposal

## Design origin

Consulted: Architect agent (Option E recommendation), Designer agent (UI hierarchy and component spec). See IMPLEMENTATION_PLAN.md for the full contracts.

---

## Cross-process communication topology

```
Python process                          Electron main                React renderer
  http_server.py                          terminal.ts               useHQ.tsx
       │                                      │                         │
       │ SSE: TERMINAL_SPAWN ──────────────────────────────────────►   │
       │                                      │ ◄─ terminal.spawn() ─── │
       │                                      │    (IPC: node-pty)      │
       │                          PTY(claude) ◄── argv from event       │
       │ ◄─── POST /terminal/started ─────────│                         │
       │                                      │                         │
       │   (waits threading.Event)            │  output → xterm live    │
       │                                      │                         │
       │ ◄─── POST /terminal/result ──────────│  (on PTY exit)          │
       │   _loop resumes                      │                         │
       │                                      │                         │
       │ SSE: TERMINAL_SIGNAL ─────────────────────────────────────►   │
       │   (on abort)                         │ terminal.kill(tabId) ─► │
```

**Why this topology?**

- Supervisor (Python) cannot call `window.pathly.terminal.spawn()` — it's not in the same process.
- Studio (Electron renderer) cannot directly call Python subprocess methods — it's sandboxed.
- The SSE channel already exists and is the established bidirectional boundary: supervisor → Studio for events, Studio → supervisor for HTTP callbacks.
- No new transport mechanism, no second HTTP server, no file polling.

---

## Key architectural boundaries

### Boundary 1: Supervisor ↔ http_server

`http_server.py` runs in the same Python process as `supervisor.py`. The two new endpoints (`/runner/terminal/started` and `/runner/terminal/result`) reach into the supervisor module via module-level dicts:

```python
# In supervisor.py (module level, thread-safe via dict assignment)
_terminal_started_events: dict[str, threading.Event] = {}
_terminal_result_data: dict[str, dict] = {}
_terminal_result_events: dict[str, threading.Event] = {}
```

`http_server.py` imports and writes to these dicts. This is the same pattern as the existing `_active_runners` dict — no new architecture.

### Boundary 2: Supervisor ↔ Studio via SSE

All supervisor → Studio communication goes through `_broadcast_sse(payload)`. The new event types (`TERMINAL_SPAWN`, `TERMINAL_SIGNAL`, `RUNNER_WARNING`) are plain JSON payloads, identical in format to existing events. No schema registry change needed.

### Boundary 3: Studio renderer ↔ Electron main via IPC

The renderer calls `window.pathly.terminal.spawn()` (already in preload). The main process (`terminal.ts`) creates the PTY and owns the process handle. The renderer never gets the PTY file descriptor — all data flows through the `terminal:data:${tabId}` IPC channel.

### Boundary 4: terminal.ts → supervisor (result POST)

`terminal.ts` (Electron main process, Node.js) uses `fetch()` to POST the result to the HTTP server. This is the only new direction of communication. It is fire-and-forget with one retry on network error.

`terminal.ts` POSTs `stdout_tail` (raw last-64KB of PTY output) rather than attempting JSON extraction itself. Result parsing belongs to the Python adapter layer: `runner.parse_result(adapter, stdout_tail)` reuses the same output parser that `invoke_agent()` already calls on headless subprocess stdout. This keeps the renderer dumb and the adapter contract in one place.

The `user_initiated` boolean in the result POST distinguishes "agent finished" from "user killed the tab" — the supervisor treats `user_initiated: true` as a clean abort (does not increment feedback counter).

---

## State ownership

| State | Owner | Source of truth |
|---|---|---|
| PTY process handle | Electron main (terminal.ts) | `activePtys` Map |
| Terminal tab list | React renderer (terminalStore) | Zustand store |
| PTY output buffer (64KB tail) | Electron main (terminal.ts) | `ptyOutputBuf` Map |
| Runner tab metadata (run_id, topic) | Electron main (terminal.ts) | `runnerTabMeta` Map |
| Run active flag, terminal_mode | Python supervisor | `RunnerState` fields |
| threading.Events (started/result) | Python supervisor | Module-level dicts, under `_lock` |
| Stage log, logCardExpanded | React renderer (runnerStore) | Zustand store |
| studio_window_id | React renderer (module const) | UUID constant, set once at startup |
| FSM state | Python FSM (fsm_ops.py) | plans/FEATURE/STATE.json |

No state is duplicated across boundaries. Each boundary communicates state changes as events, not as polls.

---

## Headless fallback design

The headless fallback is intentional, not a workaround. It ensures the pipeline is never blocked by UI availability:

```
_run_stage_via_terminal():
  broadcast TERMINAL_SPAWN
  wait started_event[run_id] timeout=5s
  if timeout:
    broadcast RUNNER_WARNING
    return invoke_agent(...)  ← exact same contract as before
  wait result_event[run_id]  ← no timeout (stage may run for hours)
  return stored_result[run_id]
```

The fallback path has identical return type (`dict` with `cost_usd`, `session_id`, `exit_code`, token counts). The caller (`_loop`) doesn't know which path was taken.

---

## What is NOT in scope

- **Mid-stage pause**: PTY-level SIGSTOP is platform-specific (broken on Windows). Pause remains between stages only.
- **Multiple Studios competing**: First POST to `/terminal/started` wins. Duplicate PTY tabs in additional windows are cosmetic.
- **Popout runner terminal**: Runner tabs can be manually popped out via the existing `[↗]` button in PaneTabBar — no special handling needed. Lifecycle (kill on abort) still works because `terminal.ts` owns all PTYs regardless of window.
- **Interactive decision making via terminal**: DECISION_MENU still goes through the existing Advance/Reroute/Retry buttons in FlowControlBar. The terminal is for observation and ad-hoc typing only.

---

## RunnerLogCard state derivation

RunnerLogCard is a pure projection of `useRunnerStore`. It does not fetch, does not subscribe to SSE directly, and has no local state beyond the collapsed/expanded flag (stored in runnerStore, not component state, so it survives re-renders).

Stage log is populated by:
- `STAGE_CHANGE` SSE → `recordStageStart(stage, adapter, null)` ← already handled in useHQ
- `TERMINAL_SPAWN` SSE → updates the last stageLog entry with `tabId`
- `TERMINAL_SIGNAL` or `RUNNER_STATUS {status: done/error}` → `recordStageEnd(exitCode)`

The card rebuilds the duration column from `endedAt - startedAt` at render time — no pre-computed field needed.

---

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| `resolve_argv` and headless path diverge | Low | Both use same function; unit test covers argv construction |
| PTY output buffer grows unbounded | Low | Capped at last 64 KB; flow-controlled via high/low watermark |
| `result_event` never fires (network error) | Medium | One retry in terminal.ts; supervisor needs a max-stage timeout (EC-6) |
| Tab ID collision on runner restart | Low | `runnerOwned` field on TerminalTab used everywhere — no string-prefix sniffing |
| Multi-window ghost PTY | Medium | `studio_window_id` in started POST; supervisor broadcasts `TERMINAL_CLAIMED`; losing window kills orphan PTY |
| ConPTY hang on Windows (process does not exit) | Medium | `useConpty: false` configurable fallback via `PATHLY_CONPTY=0`; `node-pty` in `asarUnpack` |
| 5s dead-wait per stage between Conv 1 and Conv 2 | High (if not gated) | `TERMINAL_SPAWN` broadcast gated on `PATHLY_TERMINAL_MODE=1` env var |
| `_terminal_started_events` dict-resize race | Low | All dict mutations under `supervisor._lock` |
| SSE missed event on reconnect | Low | Python SSE server emits `id:` fields; Studio re-polls `/runner/status` on `EventSource` reconnect |
| xterm.js FitAddon crash on hidden tab | Low | Guard `fit()` with non-zero dimension check before calling on tab activation |
