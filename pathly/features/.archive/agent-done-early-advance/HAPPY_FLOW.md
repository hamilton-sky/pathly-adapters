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

---

## Happy flow — Interactive mode (Conv 4)

**Preconditions:** `PATHLY_RUNNER_INTERACTIVE=1` and `PATHLY_RUNNER_EARLY_ADVANCE=1` are both set.

1. Supervisor builds argv for the PTY **without** `--print` or `--output-format=json`.
   Claude Code opens as an interactive session the user can see and type into.

2. Watcher thread starts as in the headless happy flow (step 3 above).

3. Agent finishes its work and writes `AGENT_DONE` to EVENTS.jsonl.

4. Watcher detects the event within 0.1 s; sets `_agent_done_events[run_id]`.

5. Supervisor advances FSM with AGENT_DONE data.

6. Because `interactive=True`:
   - Supervisor emits `TERMINAL_KILL` SSE with the PTY's `tab_id`.
   - Studio receives the SSE and closes the PTY tab (the Claude Code window disappears).
   - Supervisor writes `STAGE_INTERACTIVE_DONE` event to EVENTS.jsonl.
   - All four dicts for `run_id` are cleaned up immediately.
   - **No reconciliation window is started** — the PTY was killed, so no billing POST will arrive.

7. Studio opens a new PTY for the next stage with the next stage's prompt.

**Outcome:** User sees each stage open as a live Claude Code window. The window closes
automatically when the agent is done. No orphaned processes. Cost data comes from
the AGENT_DONE event written by the agent; no external billing POST is expected.

---

## Happy flow — Pipeline History injection (Conv 5)

**Preconditions:** Several stages have already run and written AGENT_DONE to EVENTS.jsonl.

1. FSM advances to a new stage (e.g., REVIEWING after BUILDING).

2. Supervisor calls `build_prompt('team/review', topic, project_root, 'claude')`.

3. `build_prompt` composes the skill text, runs `_inject_prompt_vars`, then calls
   `build_pipeline_history_block(events_path)`.

4. `build_pipeline_history_block` reads EVENTS.jsonl, collects the last 10 AGENT_DONE
   entries, and returns:
   ```
   ## Pipeline History

   - **builder (conv 1)**: added StudioBridgeTool subclasses; tsc passes
   - **reviewer (conv 1)**: PASS — no violations found
   - **builder (conv 2)**: wired fsm:runSkill IPC and preload bridge
   ```

5. `build_prompt` appends the block to the prompt text and returns.

6. The reviewer agent receives its full instructions with the Pipeline History section
   at the bottom — it knows exactly what builder did in prior conversations without
   having to read PROGRESS.md or re-run git log.

**Outcome:** Every agent starts with a compact summary of what came before.
Token cost is low (one line per prior agent). No extra file reads needed in the agent.
