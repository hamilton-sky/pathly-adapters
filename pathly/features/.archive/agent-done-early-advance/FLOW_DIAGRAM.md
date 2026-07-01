# FLOW_DIAGRAM.md — agent-done-early-advance

## Dual-path flow: fast path (watcher) vs slow path (PTY exit)

```
_run_stage_via_terminal(run_id, stage)
         |
         |  register _terminal_result_events[run_id]   (existing)
         |  register _agent_done_events[run_id]         (new)
         |
         +--[early_advance flag ON?]--YES--> start _agent_done_watcher thread
         |                                       |
         |                                       | tail_agent_done() polling loop
         |                                       | (0.1 s intervals, tracks byte offset)
         |                                       |
         |         <---AGENT_DONE written to EVENTS.jsonl---+
         |                                       |
         |                                  set _agent_done_events[run_id]
         |
         |   RACE: wait(_agent_done_events[run_id], result_evt, timeout=1800)
         |
         |                    |                             |
         |           [AGENT_DONE fires first]       [result_evt fires first]
         |           FAST PATH                       SLOW PATH (existing)
         |                    |                             |
         |    read_last_agent_done(events_path)    read _terminal_result_data
         |    advance FSM with AGENT_DONE data      advance FSM with PTY data
         |    start _reconciliation_window()         cancel watcher (set stop_evt)
         |    return                                 cleanup all dicts
         |                    |                             |
         |                    |                             v
         |                    |                     [next stage begins]
         |                    |
         |         RECONCILIATION WINDOW (30 s)
         |                    |
         |   PTY still running in background
         |   Claude CLI exits → POST /runner/terminal/result
         |                    |
         |          _terminal_result_events[run_id].wait(timeout=30)
         |                    |
         |           +--------+--------+
         |           |                 |
         |      [POST arrived      [timeout — PTY POST
         |       within 30 s]       never arrived]
         |           |                 |
         |  record cost_usd,   write STAGE_RECONCILIATION_FAILURE
         |  session_id         to EVENTS.jsonl
         |  to EVENTS.jsonl    exit_code = -1
         |           |                 |
         |           +-----------------+
         |                    |
         |        cleanup: pop all 4 dict entries for run_id
         |
         v
    [stage complete]
```

## Key invariant (shown visually)

```
_terminal_result_events[run_id]   ←── only touched by: PTY POST handler + reconciliation thread
_terminal_result_data[run_id]     ←── only touched by: PTY POST handler + reconciliation thread

_agent_done_events[run_id]        ←── only touched by: watcher thread + race waiter
_agent_done_stop_events[run_id]   ←── only touched by: watcher thread + cleanup

              NEVER cross the streams
```

## Slow-path (flag off) — unchanged

```
_run_stage_via_terminal(run_id, stage)
         |
         |  register _terminal_result_events[run_id]   (existing)
         |  [flag is OFF — no watcher, no new dicts]
         |
         |  result_evt.wait(timeout=1800)
         |
         |  [PTY exits → POST /runner/terminal/result]
         |
         |  data = _terminal_result_data.pop(run_id)
         |  advance FSM with PTY data
         |  cleanup existing dicts
         |
         v
    [stage complete — identical to current behaviour]
```

## Thread map

```
Main supervisor thread
  └── _run_stage_via_terminal()
        ├── [IF early_advance] daemon thread: _agent_done_watcher()
        │     └── tail_agent_done() generator
        └── [AFTER early advance] daemon thread: _reconciliation_window()

HTTP server thread (separate process/thread)
  └── POST /runner/terminal/result
        └── writes _terminal_result_data[run_id]
        └── sets  _terminal_result_events[run_id]
```
