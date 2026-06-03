# IMPLEMENTATION_PLAN.md — agent-done-early-advance

## Phase 0 — Pre-flight (builder reads this first in every conversation)

Before writing any code:

1. Confirm the following imports resolve without error:
   ```
   python -c "from pathly_orchestrator.events import TYPE_AGENT_DONE; print('ok')"
   python -c "from pathly_orchestrator.runner import read_last_agent_done; print('ok')"
   python -c "from pathly_orchestrator.feature_flags import FeatureFlags; print('ok')"
   python -c "from pathly_orchestrator.supervisor import Supervisor; print('ok')"
   ```
2. Run existing test suite and confirm zero failures:
   ```
   python -m pytest tests/test_supervisor.py -q
   ```
3. Confirm env var `PATHLY_RUNNER_EARLY_ADVANCE` is NOT set in the test environment
   (test isolation requirement).
4. Glob-verify every file path in this plan exists before writing to it:
   - `src/pathly_orchestrator/events.py`
   - `src/pathly_orchestrator/runner.py`
   - `src/pathly_orchestrator/feature_flags.py`
   - `src/pathly_orchestrator/supervisor.py`
   - `tests/test_supervisor.py`

Do not proceed past Phase 0 if any import fails or any test file is missing.

---

## Phase 1 — Foundation layer (Conv 1)

### 1.1 `events.py` — Add reconciliation failure constant

**File:** `src/pathly_orchestrator/events.py`

**Done when:** `TYPE_STAGE_RECONCILIATION_FAILURE` is exported from the module.

**What to add** (after the last existing TYPE_ constant):
```python
TYPE_STAGE_RECONCILIATION_FAILURE = "STAGE_RECONCILIATION_FAILURE"
# Schema: {"type": "STAGE_RECONCILIATION_FAILURE", "topic": str, "stage": str,
#           "exit_code": int, "ts": str (ISO-8601)}
# Written when a PTY billing POST does not arrive within the reconciliation
# window after an early FSM advance.
```

**Verify:**
```
python -c "from pathly_orchestrator.events import TYPE_STAGE_RECONCILIATION_FAILURE; assert TYPE_STAGE_RECONCILIATION_FAILURE == 'STAGE_RECONCILIATION_FAILURE'; print('PASS')"
```

---

### 1.2 `feature_flags.py` — Add `early_advance` property

**File:** `src/pathly_orchestrator/feature_flags.py`

**Done when:** `FeatureFlags().early_advance` returns `False` by default and `True` when `PATHLY_RUNNER_EARLY_ADVANCE=1`.

**What to add** (use existing `_bool()` helper pattern):
```python
@property
def early_advance(self) -> bool:
    return self._bool("PATHLY_RUNNER_EARLY_ADVANCE", False)
```

**Verify:**
```
python -c "from pathly_orchestrator.feature_flags import FeatureFlags; ff = FeatureFlags(); assert ff.early_advance is False; print('PASS')"
PATHLY_RUNNER_EARLY_ADVANCE=1 python -c "from pathly_orchestrator.feature_flags import FeatureFlags; ff = FeatureFlags(); assert ff.early_advance is True; print('PASS')"
```

---

### 1.3 `runner.py` — Add `tail_agent_done()` generator

**File:** `src/pathly_orchestrator/runner.py`

**Done when:** `tail_agent_done` is importable and a unit test with a temp file passes.

**Signature:**
```python
def tail_agent_done(
    path: str,
    after_ts: str,
    stop_evt: threading.Event,
    poll_interval: float = 0.1,
) -> Generator[dict, None, None]:
```

**Behaviour contract:**
- Opens file in binary mode; tracks byte offset between polls.
- On each poll: reads new bytes from offset, splits on `\n`, parses each line as JSON.
- Yields the dict if `event["type"] == "AGENT_DONE"` and `event["ts"] >= after_ts`.
- Sleeps `poll_interval` seconds between polls.
- Exits the loop (returns) when `stop_evt.is_set()` AND no new bytes were read in the last poll.
- Never raises on missing file — waits until file exists before reading.

**Verify:**
```
python -m pytest tests/test_runner.py -k "tail_agent_done" -q
```
(builder writes this test as part of Conv 1)

---

## Phase 2 — Supervisor watcher (Conv 2)

### 2.1 `supervisor.py` — Separate signal dict and watcher thread

**File:** `src/pathly_orchestrator/supervisor.py`

**Done when:** `_agent_done_events` dict exists on the supervisor; a watcher thread is started when `feature_flags.early_advance` is True.

**New supervisor state:**
```python
self._agent_done_events: dict[str, threading.Event] = {}
```

**Watcher thread per stage run** (started only when `early_advance` is True):
```python
def _agent_done_watcher(self, run_id: str, events_path: str, start_ts: str) -> None:
    stop_evt = self._agent_done_stop_events[run_id]
    for event in tail_agent_done(events_path, start_ts, stop_evt):
        self._agent_done_events[run_id].set()
        break   # fire exactly once; guard handled by Event semantics
```

**CRITICAL invariant:** The watcher NEVER touches `_terminal_result_events`. Those two dicts are independent signal channels.

---

### 2.2 `supervisor.py` — Fast-path branch in `_run_stage_via_terminal()`

**Done when:** When `early_advance` is True and `_agent_done_events[run_id]` fires, the supervisor calls FSM advance without waiting for `result_evt`.

**Wait logic (pseudo-code):**
```python
if feature_flags.early_advance:
    # Race: whichever fires first wins
    done_evt = self._agent_done_events[run_id]
    fired_early = _wait_first(done_evt, result_evt, timeout=1800)
    if fired_early == "agent_done":
        _advance_fsm_with_agent_done_data(run_id)
        _start_reconciliation_window(run_id, timeout=30)
        return
# Slow path (existing code, unchanged)
result_evt.wait(timeout=1800)
_advance_fsm_with_result_data(run_id)
```

**Done when:** Integration test (see Phase 2.4) passes.

---

### 2.3 `supervisor.py` — Reconciliation window + billing-only update

**Done when:** After early advance, billing POST updates cost fields without re-triggering FSM advance; timeout writes `STAGE_RECONCILIATION_FAILURE`.

**Reconciliation thread** (started after early advance):
```python
def _reconciliation_window(self, run_id: str, stage: str, timeout: int = 30) -> None:
    arrived = self._terminal_result_events[run_id].wait(timeout=timeout)
    if arrived:
        data = self._terminal_result_data.get(run_id, {})
        _update_billing_fields(run_id, data.get("cost_usd"), data.get("session_id"))
    else:
        _write_event(TYPE_STAGE_RECONCILIATION_FAILURE, {
            "topic": run_id,
            "stage": stage,
            "exit_code": -1,
            "ts": _now_iso(),
        })
    # Clean up regardless
    self._terminal_result_events.pop(run_id, None)
    self._terminal_result_data.pop(run_id, None)
    self._agent_done_events.pop(run_id, None)
```

**Verify:** See Phase 2.4 tests.

---

### 2.4 `tests/test_supervisor.py` — Three new watcher tests

**Done when:** All three tests pass; existing tests still pass.

**Test 1 — Fast path with reconciliation:**
- Mock EVENTS.jsonl with an AGENT_DONE written immediately.
- Mock PTY POST arriving within 5 seconds.
- Assert FSM advance called once.
- Assert no STAGE_RECONCILIATION_FAILURE written.

**Test 2 — Timeout path:**
- Mock EVENTS.jsonl with an AGENT_DONE written immediately.
- Mock PTY POST never arriving (timeout mock set to 0.1 s for test speed).
- Assert FSM advance called once.
- Assert STAGE_RECONCILIATION_FAILURE written to EVENTS.jsonl.

**Test 3 — Slow path (flag off):**
- `PATHLY_RUNNER_EARLY_ADVANCE` not set.
- Mock PTY POST arriving normally.
- Assert FSM advance called once via existing path.
- Assert no watcher thread started.

**Verify:**
```
python -m pytest tests/test_supervisor.py -q
```

---

## Phase 3 — Studio SSE pill (Conv 3, optional)

### 3.1 `terminal.ts` — Emit `TERMINAL_AGENT_DONE` SSE

**File:** `studio/src/main/ipc/terminal.ts`

**Done when:** When the Python watcher fires early, the supervisor emits a `TERMINAL_AGENT_DONE` SSE event; Studio renders a "finalizing..." status pill for the active stage.

**Scope:** No changes to PTY spawn, PTY exit handler, or `/runner/terminal/result` POST logic.

**Verify:**
```
cd studio && npx tsc --noEmit
```

---

## Reconciliation failure policy

When a `STAGE_RECONCILIATION_FAILURE` event is written:
- The FSM advance has already occurred — no rollback.
- Cost for the stage is treated as unknown (0.0 USD) in pipeline cost totals.
- The Studio UI does NOT block on reconciliation failure; it shows a warning icon on the stage tile.
- Operators can inspect EVENTS.jsonl to confirm the failure event.
- This is a best-effort billing safeguard, not a correctness gate.

---

## CANDIDATE-006 — Exact event schema (embedded)

```json
{
  "type": "STAGE_RECONCILIATION_FAILURE",
  "topic": "<run_id string>",
  "stage": "<stage name string, e.g. BUILD>",
  "exit_code": -1,
  "ts": "2026-06-03T12:34:56.789Z"
}
```

Fields:
- `type` — always `"STAGE_RECONCILIATION_FAILURE"` (use the constant)
- `topic` — the run_id used as routing key throughout the supervisor
- `stage` — the FSM stage name at time of failure
- `exit_code` — PTY exit code if received, `-1` if never received
- `ts` — ISO-8601 UTC timestamp at time of writing the event
