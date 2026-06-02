# visible-runner — User Stories

## S1: Live terminal tab per stage

**As a developer** using the Pathly Studio, when the autonomous runner starts a pipeline stage, I want a named terminal tab to open automatically in PaneTabBar so I can see the AI agent working live in xterm.

**Acceptance criteria:**
- AC 1.1: When the runner starts a new stage, a tab labeled `[adapter] — [stage]` (e.g. `claude — discover`) opens in PaneTabBar within 5 seconds and becomes the active tab.
- AC 1.2: The tab has a 2px teal left border (CSS class `.runnerTab`) distinguishing it from manually opened tabs.
- AC 1.3: The agent's CLI output appears in the xterm viewport in real time.
- AC 1.4: Each stage opens a new tab; previous stage tabs remain open.
- AC 1.5: When a stage completes, a `── [adapter] — [stage]  DONE ──` text line appears in the terminal buffer (written to xterm directly, not to the PTY stdin).
- AC 1.6: After the stage completes, the tab status dot shows green (done state).

---

## S2: User can type to intervene

**As a developer**, I want to type in the active runner terminal to intervene in the agent mid-stage, with a non-blocking ANSI warning on first focus.

**Acceptance criteria:**
- AC 2.1: The user can type in the terminal and keystrokes are forwarded to the agent PTY process.
- AC 2.2: The first time the user clicks into a runner-active terminal (per stage), a yellow ANSI message appears: `[!] Autonomous mode active — input will be forwarded to the agent`.
- AC 2.3: The warning does not repeat on subsequent keystrokes in the same stage.

---

## S3: Runner lifecycle controls work with terminal tabs

**As a developer**, I want the FlowControlBar Abort button to stop the agent running in the terminal tab, and I want the pipeline to continue to the next stage when the current stage finishes in the terminal.

**Acceptance criteria:**
- AC 3.1: Clicking Abort in FlowControlBar while an agent runs in a terminal broadcasts `TERMINAL_SIGNAL {signal:"term"}` SSE; Studio kills the PTY; a `── Runner aborted ──` ANSI red line appears in the terminal buffer.
- AC 3.2: When the PTY exits (agent done), Studio POSTs `/runner/terminal/result` with `exit_code` and the last JSON line from the output buffer; the supervisor resumes the pipeline loop.
- AC 3.3: Pause takes effect after the current stage completes (the supervisor checks `_pause_flag` at stage boundaries, as today).

---

## S4: RunnerLogCard in HQ chat

**As a developer**, I want a collapsible RunnerLogCard in the HQ chat column showing stage transition history from SSE events so I can track pipeline progress without always watching the terminal.

**Acceptance criteria:**
- AC 4.1: When the runner emits its first SSE event for a run, a RunnerLogCard appears in the HQ chat column (sticky above the input bar, not inside the message list).
- AC 4.2: Collapsed state shows: pulsing status dot + stage count summary (e.g. `3 stages done — REVIEWING`) + `[▾]` expand toggle + `[Jump ↗]` button.
- AC 4.3: Expanded state shows a table with columns: stage name, adapter, timestamp, duration, status (done/running/error); plus a footer row with run start time, total stages, and cumulative cost.
- AC 4.4: One RunnerLogCard per pipeline run is appended; a new run appends a new card below prior ones.
- AC 4.5: After the pipeline finishes, the card un-stickies and remains as a static record in the chat column.

---

## S5: Live jump button

**As a developer**, I want a `[live ↗]` button in StageStatusStrip that instantly focuses the active runner terminal tab.

**Acceptance criteria:**
- AC 5.1: When `status === 'running'`, StageStatusStrip renders a `[live ↗]` pill button (teal background, teal border, 10px font) to the right of the adapter chip.
- AC 5.2: Clicking the button opens the terminal pane and sets the active tab to the current runner tab (calls `useTerminalStore.getState().openTab(activeRunnerTabId)`).
- AC 5.3: The `[Jump ↗]` button in RunnerLogCard performs the same action (shared logic).
- AC 5.4: When `status !== 'running'`, the button is not rendered (no empty placeholder).

---

## S6: Decision point visibility

**As a developer**, I want to be immediately notified when the runner reaches a DECISION_MENU point so I don't miss that it's waiting for my input.

**Acceptance criteria:**
- AC 6.1: When `DECISION_MENU` SSE fires, the RunnerLogCard auto-expands (sets `logCardExpanded: true` in runnerStore).
- AC 6.2: A toast with message "Runner is waiting for your decision" appears for 4 seconds (uses existing `useToastStore.push()`).

---

## S7: Headless fallback when Studio is not connected

**As a developer** running the pipeline without Studio open, I want the runner to fall back to headless mode automatically so the pipeline never blocks on UI state.

**Acceptance criteria:**
- AC 7.1: If no `/runner/terminal/started` callback arrives within 5 seconds of broadcasting `TERMINAL_SPAWN`, the supervisor logs a warning and falls back to `invoke_agent()` for that stage.
- AC 7.2: The fallback path produces the same FSM state transition as the normal terminal path (DONE or ERROR).
- AC 7.3: A `RUNNER_WARNING` SSE event is broadcast when fallback triggers: `{type: "RUNNER_WARNING", topic, reason: "terminal_spawn_timeout", stage}`.
