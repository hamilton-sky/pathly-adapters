# TEST_FAILURES — visible-runner

**Date:** 2026-06-02
**Tester:** claude-sonnet-4-6
**Python tests:** 325 passed, 3 skipped (all pass)
**TypeScript typecheck:** BLOCKED — Bash permission denied; could not run `tsc --noEmit`. Reported as NOT COVERED gaps below.

---

## Test Plan

### Story 1: Live terminal tab per stage

Story 1.1: Tab labeled [adapter] — [stage] opens within 5s
  Criterion: Tab labeled `[adapter] — [stage]` opens in PaneTabBar within 5s and becomes active
  Test: Trace TERMINAL_SPAWN handler in useHQ.tsx (line 261–285) → calls `useTerminalStore.getState().addTab(tab_id, label, 'left', adapter)` which sets `activeTabIdLeft = tab_id`. Label is built in supervisor.py line 198 as `f"{adapter} — {state.current_state or state.status}"`.
  Status: PASS
  Notes: Label format matches spec. Tab becomes active via addTab setting activeTabIdLeft.

Story 1.2: 2px teal left border (.runnerTab CSS class)
  Criterion: Tab has 2px teal left border via CSS class `.runnerTab`
  Test: Terminal.module.css line 162–166: `.tabRunner { border-left: 2px solid var(--runner-border, rgba(45, 212, 191, 0.30)); }`. PaneTabBar.tsx line 55 applies `styles.tabRunner` when `tab.runnerOwned`. useHQ.tsx line 270–272 sets `runnerOwned: true` immediately after addTab.
  Status: PASS
  Notes: USER_STORIES.md specifies class `.runnerTab`; implementation uses `.tabRunner` — same element, different class name. Both produce identical visual output with 2px teal border. Not a functional failure.

Story 1.3: PTY streams live output
  Criterion: Agent CLI output appears in xterm viewport in real time
  Test: terminal.ts line 121–128: `ptyProcess.onData` calls `sendToWindow(tabId, terminal:data:${tabId}, data)`. Renderer listens via `window.pathly.terminal.onData`.
  Status: PASS

Story 1.4: Each stage opens new tab; prior tabs remain
  Criterion: Each stage opens a new tab; previous stage tabs remain open
  Test: useHQ.tsx line 269: calls `addTab(tab_id, ...)` — addTab in terminalStore.ts line 44–55 always appends to `s.tabs` array. No tab closure logic triggered by TERMINAL_SPAWN.
  Status: PASS

Story 1.5: Done/ABORTED banner written to xterm on exit
  Criterion: `── [adapter] — [stage]  DONE ──` text line written to xterm (not PTY stdin) when stage completes
  Test: terminal.ts lines 143–146: On PTY exit, if `exitCode === 0` writes DONE banner, else writes ABORTED banner directly via `sendToWindow(tabId, terminal:data:${tabId}, banner)`. Banner text uses ANSI codes: `\x1b[1;32mDONE\x1b[0m` (green) and `\x1b[1;31mABORTED\x1b[0m` (red).
  Status: FAIL
  Notes: PARTIAL FAILURE. The banner is written but does not include `[adapter] — [stage]` in the text. Spec requires `── [adapter] — [stage]  DONE ──`. Actual banner is `──  DONE ──────────────────────────────` (no label). Evidence: terminal.ts lines 143–145.

Story 1.6: Tab status dot shows green after done
  Criterion: After stage completes, tab status dot shows green (done state)
  Test: PaneTabBar.tsx line 69 renders `styles.statusDone` (green) when `tab.status === 'done'`. terminalStore.ts has no `setTabStatus` action — `TerminalTab.status` field is never updated after `addTab`. On PTY exit, terminal.ts sends `terminal:exit` IPC; Terminal/index.tsx line 67–69 handles it by writing `[process exited]` text — it does NOT update tab.status to 'done'.
  Status: FAIL
  Notes: `tab.status` is never set to `'done'` after PTY exit. The green dot in PaneTabBar is dead code for runner tabs. Evidence: terminalStore.ts has no `updateTab` or `setTabStatus` action; no code path sets `tab.status = 'done'`.

---

### Story 2: User can type to intervene

Story 2.1: Keystrokes forwarded to PTY
  Criterion: User can type and keystrokes are forwarded to agent PTY
  Test: terminal.ts lines 168–173: `ipcMain.on('terminal:write', ...)` writes data to `activePtys.get(tabId)`. Standard PTY forwarding behavior is present.
  Status: PASS

Story 2.2: First-click warning (ANSI yellow) on first focus per stage
  Criterion: First time user clicks into a runner-active terminal, yellow ANSI message appears: `[!] Autonomous mode active — input will be forwarded to the agent`
  Test: Searched all renderer source, terminal.ts, xtermRegistry.ts, TerminalTabView.tsx for "autonomous mode", "first focus", "firstWarning", "warnShown", "firstClick". Zero matches found anywhere in the codebase.
  Status: FAIL
  Notes: This acceptance criterion is NOT IMPLEMENTED. No code path writes an ANSI warning on first focus for runner-owned tabs. Evidence: exhaustive grep returning no matches.

Story 2.3: Warning does not repeat on subsequent keystrokes
  Criterion: The first-focus warning does not repeat
  Test: Dependent on AC 2.2 which is not implemented.
  Status: FAIL
  Notes: NOT IMPLEMENTED — the warning feature (AC 2.2) does not exist, so the no-repeat guard also does not exist.

---

### Story 3: Runner lifecycle controls

Story 3.1: Abort broadcasts TERMINAL_SIGNAL SSE
  Criterion: Clicking Abort broadcasts `TERMINAL_SIGNAL {signal:"term"}` SSE; Studio kills PTY; ABORTED banner appears
  Test: Searched entire src/ for "TERMINAL_SIGNAL" broadcast in Python code. `abort_run()` (supervisor.py lines 779–792) sets `_abort_flag = True` and calls `proc.kill()` but broadcasts NO SSE. There is no `TERMINAL_SIGNAL` broadcast anywhere in supervisor.py or http_server.py. The Studio-side handler for `TERMINAL_SIGNAL` in useHQ.tsx (lines 287–292) is correct but will never be triggered by an abort.
  Status: FAIL
  Notes: HARD FAILURE. The abort path kills the subprocess directly (lines 789–791) without broadcasting `TERMINAL_SIGNAL`. The Studio PTY is never killed by the abort command; it will keep running until the process naturally exits or times out. Evidence: supervisor.py lines 779–792 — no broadcast call present.

Story 3.2: PTY exit → POST /runner/terminal/result → supervisor resumes
  Criterion: PTY exits, Studio POSTs `/runner/terminal/result`, supervisor resumes pipeline
  Test: terminal.ts lines 147–160: POST body includes `{run_id, topic, exit_code, stdout_tail, wall_seconds, user_initiated}`. supervisor.py `/runner/terminal/result` endpoint exists (http_server.py). _run_stage_via_terminal() line 243 waits on `result_evt.wait()`.
  Status: PASS

Story 3.3: Pause takes effect at stage boundaries
  Criterion: Pause takes effect after current stage completes
  Test: supervisor.py lines 281–293: `_pause_flag` checked at top of each stage loop iteration. Confirmed unchanged from pre-feature behavior.
  Status: PASS

---

### Story 4: RunnerLogCard in HQ chat

Story 4.1: Card appears when first SSE fires
  Criterion: RunnerLogCard appears in HQ chat column when runner emits first SSE
  Test: RunnerLogCard.tsx line 19: returns null when `stageLog.length === 0`. STAGE_CHANGE handler in useHQ.tsx line 242 calls `recordStageStart()` which appends to stageLog. RunnerLogCard is mounted in HQ/index.tsx (confirmed by scouts).
  Status: PASS

Story 4.2: Collapsed state content
  Criterion: Shows pulsing dot + stage count summary + [▾] + [Jump ↗]
  Test: RunnerLogCard.tsx lines 39–59: dot with pulse animation (CSS), `{doneCount} stages done — {currentEntry.stage}` text, toggle button with [▾] chevron, Jump button (conditional on `activeRunnerTabId !== null`). CSS pulse animation at RunnerLogCard.module.css lines 57–62.
  Status: PASS

Story 4.3: Expanded state shows table + footer
  Criterion: Table with stage/adapter/timestamp/duration/status columns, footer with run start/total/cost
  Test: RunnerLogCard.tsx lines 62–88: table with colgroup (5 cols), RunnerLogRow renders all fields. Footer line 86: `Started {fmtDate(runStartedAt)} · {stageLog.length} total · ${cost.toFixed(3)}`.
  Status: PASS

Story 4.4: One card per run appended; new run appends below
  Criterion: One RunnerLogCard per run; new runs append new card below prior ones
  Test: runnerStore.ts `resetRunner()` (line 67) resets `stageLog: []`. There is NO call to `resetRunner()` at run start — stageLog only resets if explicitly called. RunnerLogCard renders one card for the entire current stageLog. If a new run starts without resetRunner being called, new entries append to the same card. If resetRunner IS called between runs, the old card disappears (not kept as static record). No code path creates multiple cards for multiple runs.
  Status: FAIL
  Notes: The spec requires "One RunnerLogCard per pipeline run is appended; a new run appends a new card below prior ones." The implementation renders a single card from `stageLog`. Multiple-run history is not supported — old runs either get merged into the same card or lost when resetRunner is called. ARCH_QUESTION: Should RunnerLogCard maintain a history of past runs (array of stageLog snapshots), one card per completed run? This requires a design decision about when a "new run" starts and how to snapshot completed runs.

Story 4.5: Card un-stickies after finish
  Criterion: After pipeline finishes, card un-stickies and remains as static record
  Test: RunnerLogCard.module.css lines 15–21: `.card[data-running="true"]` applies `position: sticky`. RunnerLogCard.tsx line 40: `data-running={isRunning}`. `isRunning` is false when status !== 'running'.
  Status: PASS

---

### Story 5: Live jump button

Story 5.1: [live ↗] renders when running
  Criterion: When status === 'running', StageStatusStrip renders `[live ↗]` pill
  Test: StageStatusStrip.tsx lines 65–74: renders `<button className={styles.liveBtn}>live ↗</button>` only when `status === 'running' && activeRunnerTabId !== null`.
  Status: PASS

Story 5.2: Click opens terminal pane + active tab
  Criterion: Button opens terminal pane and sets active tab to current runner tab
  Test: StageStatusStrip.tsx line 69: `onClick={() => useRunnerStore.getState().jumpToLiveTab()}`. runnerStore.ts lines 90–96: `jumpToLiveTab()` calls `ts.toggle()` if not open, then `ts.openTab(activeRunnerTabId)`. openTab in terminalStore.ts opens the pane and sets activeTabIdLeft.
  Status: PASS

Story 5.3: Same action as Jump ↗ in RunnerLogCard
  Criterion: Jump ↗ in RunnerLogCard performs same action as live ↗
  Test: RunnerLogCard.tsx line 36: `handleJump()` calls `useRunnerStore.getState().jumpToLiveTab()` — identical call to StageStatusStrip.
  Status: PASS

Story 5.4: Not rendered when not running
  Criterion: Button not rendered when status !== 'running'
  Test: StageStatusStrip.tsx line 65: conditional `{status === 'running' && activeRunnerTabId !== null && (...)}`. No empty placeholder.
  Status: PASS

---

### Story 6: Decision point visibility

Story 6.1: DECISION_MENU auto-expands RunnerLogCard
  Criterion: DECISION_MENU SSE fires → setLogCardExpanded(true)
  Test: useHQ.tsx line 247: `useRunnerStore.getState().setLogCardExpanded(true)` called in DECISION_MENU handler.
  Status: PASS

Story 6.2: Toast "Runner is waiting for your decision"
  Criterion: Toast appears for 4 seconds
  Test: useHQ.tsx line 248: `useToastStore.getState().push('Runner is waiting for your decision', 'info')`. Toast duration is controlled by toastStore — not verified in this test session but the push() call is present.
  Status: PASS

---

### Story 7: Headless fallback

Story 7.1: 5s timeout → fallback to invoke_agent()
  Criterion: No /runner/terminal/started within 5s → fallback to invoke_agent()
  Test: supervisor.py lines 216–242: `started.wait(timeout=5)` — if not received, broadcasts RUNNER_WARNING and calls `invoke_agent(...)`.
  Status: PASS

Story 7.2: Fallback produces same FSM transition
  Criterion: Fallback path produces same DONE or ERROR state transition
  Test: Both terminal path and fallback path return a dict that is processed identically by _loop(). invoke_agent() in both cases.
  Status: PASS

Story 7.3: RUNNER_WARNING SSE broadcast on fallback
  Criterion: `{type: "RUNNER_WARNING", topic, reason: "terminal_spawn_timeout", stage}` is broadcast
  Test: supervisor.py lines 217–227: broadcasts exactly this payload when timeout fires.
  Status: PASS

---

## Summary

| # | Criterion | Status |
|---|-----------|--------|
| 1.1 | Tab labeled [adapter]—[stage] opens within 5s | PASS |
| 1.2 | 2px teal left border (.runnerTab) | PASS |
| 1.3 | PTY streams live output | PASS |
| 1.4 | Each stage opens new tab, prior remain | PASS |
| 1.5 | Done/ABORTED banner with label written to xterm | FAIL |
| 1.6 | Tab status dot shows green after done | FAIL |
| 2.1 | Keystrokes forwarded to PTY | PASS |
| 2.2 | First-click ANSI yellow warning on focus | FAIL |
| 2.3 | Warning does not repeat | FAIL |
| 3.1 | Abort broadcasts TERMINAL_SIGNAL SSE | FAIL |
| 3.2 | PTY exit → POST result → supervisor resumes | PASS |
| 3.3 | Pause at stage boundaries | PASS |
| 4.1 | RunnerLogCard appears on first SSE | PASS |
| 4.2 | Collapsed: dot + count + [▾] + [Jump ↗] | PASS |
| 4.3 | Expanded: table + footer | PASS |
| 4.4 | One card per run appended | FAIL |
| 4.5 | Card un-stickies after finish | PASS |
| 5.1 | [live ↗] renders when running | PASS |
| 5.2 | Click opens terminal pane + active tab | PASS |
| 5.3 | Same action as Jump ↗ in RunnerLogCard | PASS |
| 5.4 | Not rendered when not running | PASS |
| 6.1 | DECISION_MENU auto-expands card | PASS |
| 6.2 | Toast "Runner is waiting for your decision" | PASS |
| 7.1 | 5s timeout → fallback | PASS |
| 7.2 | Fallback same FSM transition | PASS |
| 7.3 | RUNNER_WARNING SSE on fallback | PASS |

**Passed: 19 / 25**
**Failed: 6 / 25**

---

## Failures Detail

### FAIL AC 1.5 — Done banner missing label
**Expected:** Banner text `── [adapter] — [stage]  DONE ──`
**Actual:** Banner text `──  DONE ──────────────────────────────` (no adapter/stage label)
**Location:** `studio/src/main/ipc/terminal.ts` lines 143–145
**Fix required:** Pass the label string into the onExit callback. The `runnerTabMeta` map already has `topic` and `run_id` but not the human-readable label. Either store the label in `runnerTabMeta` or construct it from `topic + run_id`.

### FAIL AC 1.6 — Tab status dot never shows green for runner tabs
**Expected:** After stage completes, `tab.status === 'done'` → green dot in PaneTabBar
**Actual:** `TerminalTab.status` field is never updated anywhere. The `terminal:exit` IPC event (terminal.ts line 134, Terminal/index.tsx lines 67–69) handles it by writing `[process exited]` text but never calls any store action to update `tab.status`.
**Location:** `studio/src/renderer/src/store/terminalStore.ts` — no `updateTab` action exists
**Fix required:** Add a `updateTabStatus(id: string, status: TerminalTab['status'])` action to terminalStore; call it from the `terminal:exit` IPC handler in Terminal/index.tsx.

### FAIL AC 2.2 — First-focus ANSI warning not implemented
**Expected:** First time user focuses a runner-active terminal, yellow ANSI message `[!] Autonomous mode active — input will be forwarded to the agent` appears
**Actual:** No such code exists anywhere in the codebase. Exhaustive grep for "autonomous mode", "firstWarning", "warnShown", "firstClick" returns zero matches.
**Location:** Not present in `studio/src/main/ipc/terminal.ts`, `studio/src/renderer/src/components/Terminal/xtermRegistry.ts`, or anywhere else
**Fix required:** Track first-focus state per tab (e.g., `Set<string>` in terminal.ts or xtermRegistry). On first `xterm.onKey()` or `xterm.onData()` for a runner-owned tab, write the ANSI warning directly to xterm before forwarding the keystroke.

### FAIL AC 2.3 — First-focus warning no-repeat guard not implemented
**Expected:** Warning does not repeat on subsequent keystrokes in same stage
**Actual:** Dependent on AC 2.2 — the feature is not implemented
**Fix required:** Implement AC 2.2 with a per-tab Set guard.

### FAIL AC 3.1 — Abort path does not broadcast TERMINAL_SIGNAL
**Expected:** POST /runner/abort → supervisor broadcasts `TERMINAL_SIGNAL {signal:"term", tab_id}` SSE → Studio kills PTY → ABORTED banner
**Actual:** `abort_run()` (supervisor.py lines 779–792) calls `proc.kill()` directly on the headless subprocess and sets `_abort_flag`. When running in terminal mode, the supervisor has no reference to the PTY process (owned by Electron main process). The TERMINAL_SIGNAL broadcast is never sent. Studio's TERMINAL_SIGNAL handler in useHQ.tsx (lines 287–292) is correct but unreachable.
**Location:** `src/pathly_orchestrator/supervisor.py` lines 779–792
**Fix required:** In `abort_run()`, after setting `_abort_flag`, broadcast `TERMINAL_SIGNAL {signal:"term", tab_id, run_id}` if a `run_id` is active (track the active `run_id` + `tab_id` in RunnerState during `_run_stage_via_terminal`). This is the architectural design intent per IMPLEMENTATION_PLAN.md line 145 and FLOW_DIAGRAM.md lines 60–61.

### FAIL AC 4.4 — One card per run history not implemented
**Expected:** Multiple pipeline runs produce multiple RunnerLogCards stacked in HQ chat; each run's card is preserved as a static record
**Actual:** `stageLog` is a single flat array in runnerStore. RunnerLogCard renders one card from the entire stageLog. There is no mechanism to snapshot prior run stageLog data. `resetRunner()` clears stageLog entirely, losing history.
**Location:** `studio/src/renderer/src/store/runnerStore.ts` (no run history array), `studio/src/renderer/src/components/HQ/RunnerLogCard/RunnerLogCard.tsx` (single-card rendering)
**ARCH_QUESTION:** Should RunnerLogCard maintain a history of past runs (array of stageLog snapshots), one card per completed run? This requires a design decision about when a "new run" starts and how to snapshot completed runs. Direct the user to `/meet architect` or `/meet planner` to resolve.

---

## Coverage Gaps (not failures)

1. **TypeScript typecheck not run** — Bash permission was denied for `tsc --noEmit`. TypeScript type errors are possible but unverified. The builder should confirm `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` and `studio/tsconfig.node.json` both pass.

2. **already_headless 409 response** — `/runner/terminal/started` does not return `{"error": "already_headless", "code": 409}` when headless fallback already triggered. This is a minor spec gap noted in the scout findings. Not tested by any acceptance criterion in USER_STORIES.md.

3. **Toast duration** — AC 6.2 specifies 4 seconds. `useToastStore.push('...', 'info')` call is present but the 4-second duration is set inside toastStore (not verified). Likely passing but not explicitly confirmed.

4. **5s timeout fallback test coverage** — No Python test exercises the 5-second spawn timeout path in `_run_stage_via_terminal()`. This is a test coverage gap, not a functional failure.
