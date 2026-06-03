# HAPPY_FLOW.md — agent-done-early-advance

## Preconditions

- `PATHLY_RUNNER_EARLY_ADVANCE=1` is set in the orchestrator environment.
- A pipeline run is active and the current stage has spawned a PTY.
- The agent inside the PTY is writing to EVENTS.jsonl as it works.

## Step-by-step narrative

1. Supervisor calls `_run_stage_via_terminal(run_id, stage, ...)`.

2. Before entering the wait, supervisor registers `_terminal_result_events[run_id]`
   (existing) and `_agent_done_events[run_id]` (new, separate dict).

3. Because `feature_flags.early_advance` is True, supervisor starts a daemon thread:
   `_agent_done_watcher(run_id, events_path, start_ts)`.

4. The watcher calls `tail_agent_done(events_path, start_ts, stop_evt)` and blocks
   in its poll loop, checking for new `AGENT_DONE` lines.

5. The agent finishes its reasoning. It writes:
   ```json
   {"type":"AGENT_DONE","summary":"Built auth module","ts":"2026-06-03T12:00:00Z"}
   ```
   to EVENTS.jsonl.

6. Within `poll_interval` (0.1 s default), `tail_agent_done` yields the event.

7. The watcher sets `_agent_done_events[run_id]`.

8. Back in `_run_stage_via_terminal`, the race detects `_agent_done_events[run_id]`
   fired first (before `result_evt`).

9. Supervisor calls `read_last_agent_done(events_path)` to get the AGENT_DONE data,
   then calls FSM advance with that data. The FSM moves to the next stage.

10. Supervisor starts `_reconciliation_window(run_id, stage, timeout=30)` as a
    daemon thread and returns from `_run_stage_via_terminal`.

11. The next stage begins immediately — the PTY for the previous stage is still
    running in the background.

12. Meanwhile the PTY process exits. The Claude CLI makes its POST to
    `/runner/terminal/result` with `cost_usd=0.042` and `session_id=abc123`.

13. The `/runner/terminal/result` handler finds `_terminal_result_events[run_id]`
    still present (never removed by the watcher), writes to `_terminal_result_data`,
    and sets the event. Returns 200 to the CLI.

14. The reconciliation window thread wakes up (within 30 s), reads `cost_usd` and
    `session_id` from `_terminal_result_data[run_id]`, writes a billing update to
    EVENTS.jsonl.

15. Reconciliation window cleans up all four dict entries for this run_id.

## Outcome

- FSM advanced within ~0.1 s of AGENT_DONE being written.
- PTY billing data recorded without loss.
- No `STAGE_RECONCILIATION_FAILURE` event in the log.
- The next stage started while the PTY was still running its teardown.
