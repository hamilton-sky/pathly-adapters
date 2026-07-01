# ARCHITECTURE_PROPOSAL.md — agent-done-early-advance

## ADR-001 — Early FSM Advance on AGENT_DONE Detection

**Status:** Accepted (scout findings, 2026-06-03)
**Decision:** Option C — Separate signal dicts with reconciliation window

---

## Options considered

### Option A — Kill PTY on early advance
Advance the FSM and immediately kill the PTY process.
**Rejected:** Billing POST never arrives; `cost_usd` and `session_id` are lost.

### Option B — Single shared event dict
Reuse `_terminal_result_events` for both early advance and billing signalling.
**Rejected:** If the watcher pops `run_id` from `_terminal_result_events` early,
the PTY's `/runner/terminal/result` POST returns 404 and billing data is lost.
The scout finding at `http_server.py` lines 988–1041 confirmed this failure mode.

### Option C — Separate signal dicts (chosen)
Add `_agent_done_events` and `_agent_done_stop_events` as independent dicts.
`_terminal_result_events` is never touched by the watcher.

**Reasons:**
1. The PTY billing POST path stays intact — it always finds its event in
   `_terminal_result_events` as long as the reconciliation window is open.
2. The two concerns (FSM advance timing, billing reconciliation) are decoupled.
3. Adding two new dicts is minimal surface area; no existing data structure is changed.
4. Rollback is simple: remove the feature flag and the two new dicts; the slow path
   code is unchanged.

---

## Separate signal dict design

```
_terminal_result_events   dict[run_id, threading.Event]   EXISTING — PTY billing signal
_terminal_result_data     dict[run_id, dict]               EXISTING — PTY billing payload
_agent_done_events        dict[run_id, threading.Event]    NEW — watcher signal
_agent_done_stop_events   dict[run_id, threading.Event]    NEW — watcher shutdown signal
```

Invariant: the watcher reads and writes only `_agent_done_events` and
`_agent_done_stop_events`. It never reads or writes `_terminal_result_events` or
`_terminal_result_data`.

---

## Reconciliation window design

After early advance, a reconciliation thread waits on `_terminal_result_events[run_id]`
for a configurable timeout (default 30 seconds).

```
timeline:
  t=0       AGENT_DONE detected by watcher
  t=0       FSM advance called
  t=0       reconciliation window thread starts (30 s countdown)
  t=2       PTY exits, billing POST arrives → reconciliation thread wakes, records data
  t=2       cleanup: all four run_id entries popped

  (failure scenario)
  t=30      reconciliation window expires without PTY POST
  t=30      STAGE_RECONCILIATION_FAILURE written to EVENTS.jsonl
  t=30      cleanup: all four run_id entries popped
```

The 30-second window is generous. PTY shutdown typically completes in 1–5 seconds.
The window exists to handle slow network or heavily loaded systems.

---

## Feature flag pattern

```python
# feature_flags.py
@property
def early_advance(self) -> bool:
    return self._bool("PATHLY_RUNNER_EARLY_ADVANCE", False)
```

- Default: off. Operators opt in by setting the env var.
- The property reads `os.environ` on each call — no caching, no restart required
  to change the flag between pipeline runs (though mid-stage changes take effect
  only on the next stage).
- The flag controls both the watcher thread start and the reconciliation window.
  There is no partial enablement.

---

## `tail_agent_done` polling design

- Binary file open (`rb`) for Windows compatibility.
- Byte offset tracked between polls — no re-reading of already-seen data.
- Partial lines (written mid-poll) held until next poll completes the `\n`.
- JSON parse errors silently skipped.
- `stop_evt` checked after each poll; generator returns when set and no new bytes remain.
- Default `poll_interval=0.1` s gives ~100 ms detection latency, well within UX tolerance.

---

## What is NOT in scope

- PTY process lifecycle management — the PTY is not killed, paused, or signalled.
- FSM rollback on non-zero PTY exit after early advance — early advance is final.
- Caching or persisting reconciliation state across orchestrator restarts.
- Changing the SSE protocol between supervisor and Studio (Conv 3 is additive only).
