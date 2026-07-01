# visible-runner — Edge Cases

## EC-1: Studio not connected (headless fallback)

**Trigger:** Supervisor broadcasts `TERMINAL_SPAWN` but no Studio client is listening to the SSE stream, or Studio is open but hasn't registered for the topic.

**Failure mode:** `started_event[run_id]` times out after 5 seconds. Pipeline blocks until timeout, then resumes in headless mode.

**Mitigation:**
- Timeout is 5 seconds — acceptable latency for a stage that may run for minutes.
- Supervisor broadcasts `RUNNER_WARNING {reason: "terminal_spawn_timeout"}` so the user knows.
- `invoke_agent()` (headless) produces identical FSM state transitions — no correctness loss.
- Test: mock the SSE client to not send `/terminal/started`; verify `_run_stage_via_terminal` falls back and returns same structure as `invoke_agent`.

---

## EC-2: PTY spawn fails (CLI not found)

**Trigger:** `window.pathly.terminal.spawn(tab_id, cwd, "claude")` fails because `claude` is not in the PATH.

**Failure mode:** PTY exits immediately with a non-zero code. `terminal.ts` exit handler fires with `exitCode ≠ 0`. `stdout_tail` will be empty or contain only the shell error message.

**Mitigation:**
- `terminal.ts` still POSTs `/runner/terminal/result {exit_code: 1, stdout_tail: "", wall_seconds: ...}`.
- Supervisor calls `runner.parse_result(adapter, stdout_tail)` — empty output returns `{"cost_usd": 0, "session_id": None}` without raising.
- Supervisor treats `exit_code != 0` as a subprocess error — same as today's headless error path.
- `RUNNER_ERROR` SSE fires; StageStatusStrip shows red dot; `errorMessage` is set.
- Resolution: user fixes PATH, then clicks Retry.

---

## EC-3: Agent produces no JSON in output

**Trigger:** Agent writes non-JSON output (e.g., hits an auth error and prints a plain-text error message, or the `--output-format=json` flag is not supported by this adapter version).

**Failure mode:** `stdout_tail` contains no parseable JSON. `parse_result()` returns `{"cost_usd": 0, "session_id": None}` (the empty-output fallback defined in Phase 1 test case 3).

**Mitigation:**
- `terminal.ts` POSTs `stdout_tail` as-is — it never attempts JSON parsing. Python's `parse_result(adapter, stdout_tail)` handles the degraded case gracefully: `cost_usd=0`, `session_id=None`.
- `RUNNER_WARNING` or `RUNNER_ERROR` depending on severity (builder to decide based on existing error handling logic).
- No crash in supervisor.

---

## EC-4: User clicks Abort mid-stage

**Trigger:** User clicks Abort in FlowControlBar while an agent is running in a terminal tab.

**Flow:**
1. `FlowControlBar` POSTs `/runner/abort`.
2. Supervisor sets `_abort_flag`.
3. Supervisor's abort handling (already in `_loop`) checks for active run_id → broadcasts `TERMINAL_SIGNAL {signal: "term"}`.
4. `useHQ` receives `TERMINAL_SIGNAL` → calls `window.pathly.terminal.kill(activeRunnerTabId)`.
5. PTY receives SIGTERM → exits with non-zero code.
6. `terminal.ts` exit handler writes the ANSI abort banner to xterm and POSTs `/runner/terminal/result {exit_code: 9, stdout_tail: "", wall_seconds: ..., user_initiated: true}`.
7. Supervisor's `result_event` fires → `_run_stage_via_terminal` returns → `_loop` sees `_abort_flag` → stops loop.

**Risk:** Race between abort flag and stage completion. If the agent finishes naturally at the same moment, `result_event` fires with `exit_code: 0` and abort flag is ignored for that stage. This is acceptable — the supervisor will check `_abort_flag` at the top of the next iteration and stop.

---

## EC-5: Two Studio instances connected (developer with two windows open)

**Trigger:** User has two Studio windows open. Both subscribe to SSE for the same topic. Both receive `TERMINAL_SPAWN`.

**Failure mode:** Both call `window.pathly.terminal.spawn()` and both POST `/runner/terminal/started`. Supervisor receives two `/terminal/started` callbacks for the same `run_id`.

**Mitigation:**
- Supervisor's `/terminal/started` handler only fires the event once (first write wins; subsequent calls for same `run_id` return `{"ok": true}` but are no-ops).
- Both Studios open a terminal tab; agent runs in both. Output is duplicated but not harmful — both are just displaying the same PTY stream.
- Both will try to POST `/terminal/result` on exit. Same deduplication applies: first POST wins.
- This is a known acceptable edge case; no special handling required for v1.

---

## EC-6: Network error on result POST

**Trigger:** `fetch` call in `terminal.ts` to `/runner/terminal/result` fails (network error, server restarted).

**Failure mode:** Supervisor's `result_event` never fires. `_run_stage_via_terminal` blocks forever.

**Mitigation:**
- Add a `cap_timeout` to the result wait — e.g., max stage duration (same as existing `max_iterations` cap logic).
- If result never arrives: supervisor emits `RUNNER_ERROR {error_kind: "terminal_result_timeout"}`, treats stage as failed.
- `terminal.ts` should retry the POST once on network error before giving up (exponential backoff not needed — one retry is sufficient).

---

## EC-7: PaneTabBar already has a tab with the same tab_id

**Trigger:** Runner crashes mid-stage and restarts, reusing the same `run_id` and therefore the same `tab_id`.

**Failure mode:** `addTab` creates a duplicate tab entry with the same ID.

**Mitigation:**
- `useHQ.tsx` TERMINAL_SPAWN handler: before calling `addTab`, check `useTerminalStore.getState().tabs.find(t => t.id === tab_id)`. If found, call `openTab(tab_id)` instead of `addTab`.
- This reuses the existing tab, which may still have the previous run's output. A new run marker line is written at the top of the reused session.

---

## EC-8: Tab is manually closed by user during a stage

**Trigger:** User clicks the [×] button on the active runner tab while the agent is still running.

**Failure mode:** PTY is killed by `closeTab` → `terminal:kill` IPC → PTY exits → `terminal.ts` exit handler fires → POSTs `/terminal/result {exit_code: 1}`. Supervisor treats as stage error.

**Mitigation:**
- This is the same as an Abort. Behavior is correct — agent is stopped, runner gets the error result.
- Optionally: add a confirmation dialog "This is a runner-owned tab — closing it will abort the current stage" (not required for v1).
