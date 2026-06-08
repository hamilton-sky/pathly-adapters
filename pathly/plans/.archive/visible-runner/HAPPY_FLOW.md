# visible-runner — Happy Flow

## Persona

Yafit opens Studio, selects the `my-new-feature` plan, and starts the autonomous runner.

## Golden Path

### 1. User starts the pipeline

Yafit clicks **Start** in FlowControlBar. The supervisor `start_run()` call launches `_loop()` in a daemon thread. StageStatusStrip shows `● my-new-feature · STORM  —  —`.

### 2. Runner broadcasts TERMINAL_SPAWN for the first stage

`_loop` calls `next_action()` → FSM returns STORM state. `_loop` calls `_run_stage_via_terminal("STORM", instructions, "claude", model, run_id)`.

Supervisor broadcasts:
```json
{ "type": "TERMINAL_SPAWN", "topic": "my-new-feature", "run_id": "abc123",
  "tab_id": "runner-abc123", "label": "claude — storm", "adapter": "claude",
  "argv": ["claude", "--output-format=json", ...], "cwd": "/project", "prompt": "..." }
```

### 3. Studio opens a terminal tab

`useHQ.tsx` receives `TERMINAL_SPAWN`:
- Calls `useTerminalStore.addTab("runner-abc123", "claude — storm", "left", "claude")`.
- Tab appears in PaneTabBar with a 2px teal left border. Terminal pane opens and the new tab is active.
- Calls `window.pathly.terminal.spawn("runner-abc123", "/project", "claude")` → PTY starts.
- After 300ms: `window.pathly.terminal.write("runner-abc123", instructions + "\n")` → prompt sent to claude.
- POSTs `/runner/terminal/started` → supervisor's `started_event["abc123"]` fires → supervisor resumes waiting for result.

StageStatusStrip updates: `● my-new-feature · STORM  claude  [live ↗]  $0.000`

### 4. User watches claude working live

Claude's output streams into the xterm viewport. Yafit can read every tool call and response in real time. She can scroll up to review earlier output.

### 5. Claude finishes STORM stage

Claude exits cleanly (exit code 0). `terminal.ts` exit handler:
- Writes the ANSI completion banner to xterm: `\r\n\x1b[2m──\x1b[0m \x1b[1;32mclaude — storm DONE\x1b[0m \x1b[2m──────────────────────────────\x1b[0m\r\n`
- POSTs `/runner/terminal/result {exit_code: 0, stdout_tail: "<last 64KB of PTY output>", wall_seconds: 3.1, user_initiated: false}`. No JSON parsing happens in terminal.ts.

Supervisor's `result_event["abc123"]` fires. `_run_stage_via_terminal` calls `runner.parse_result("claude", stdout_tail)` → extracts `{cost_usd: 0.12, session_id: "sess_abc"}`. `_loop` updates cost, increments iteration, calls `complete_stage()` → FSM advances to PLAN.

### 6. RunnerLogCard shows stage history

RunnerLogCard (sticky above input bar) shows in collapsed state: `● 1 stage done — PLAN`. Yafit clicks `[▾]` to expand:

```
STORM    claude   14:02:31   3.1s    ✓ done
PLAN   ● claude   14:02:35    —      · running
```

### 7. Pipeline continues through all stages

Each stage repeats steps 2–6, opening a new tab (`claude — plan`, `builder — build`, etc.). Each completed tab keeps its scroll history.

### 8. DECISION_MENU at REVIEW stage

Reviewer writes `REVIEW_FAILURES.md`. FSM emits `DECISION_MENU`. `useHQ` handler:
- Sets `logCardExpanded: true` → RunnerLogCard auto-expands.
- Shows toast: "Runner is waiting for your decision" (4 seconds).
- FlowControlBar decision buttons become active (orange, already implemented).

Yafit clicks **Advance** to skip, or makes the fix and clicks **Retry**.

### 9. Pipeline reaches DONE

All stages complete. Supervisor broadcasts `RUNNER_STATUS {status: "done"}`. Status dot becomes idle. RunnerLogCard un-stickies and becomes a static record. Five terminal tabs remain open, each showing their agent's output and a "DONE" end marker.

### 10. User reviews the run

Yafit clicks `[live ↗]` in StageStatusStrip → focuses the last active runner tab. She switches between tabs to compare each stage's output. She clicks `[Jump ↗]` in RunnerLogCard directly to navigate.

---

## Timing expectations

| Step | Latency |
|---|---|
| Start → first TERMINAL_SPAWN | < 500ms (FSM + broadcast) |
| TERMINAL_SPAWN → tab visible | < 1s (addTab + PTY spawn) |
| TERMINAL_SPAWN → prompt in terminal | < 1.5s (300ms delay + PTY write) |
| PTY exit → supervisor resumes | < 500ms (POST + event set) |
| Stage done → next TERMINAL_SPAWN | < 1s (FSM advance + broadcast) |
