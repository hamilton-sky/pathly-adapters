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

## Phase 4 — Interactive mode (Conv 4)

> **Depends on:** Conv 2 must be DONE. Phase 4 requires `_agent_done_events`, `tail_agent_done`, and the fast-path watcher already wired.

### 4.0 Pre-flight

```
python -c "from pathly_orchestrator.feature_flags import FeatureFlags; assert FeatureFlags().early_advance is False; print('ok')"
python -c "from pathly_orchestrator.runner import tail_agent_done; print('ok')"
python -m pytest tests/test_supervisor.py -q
```

All must pass. Do not write any code until pre-flight passes.

---

### 4.1 `events.py` — Add `STAGE_INTERACTIVE_DONE` constant

**File:** `src/pathly_orchestrator/events.py`

**What to add** (after `TYPE_STAGE_RECONCILIATION_FAILURE`):
```python
TYPE_STAGE_INTERACTIVE_DONE = "STAGE_INTERACTIVE_DONE"
# Schema: {"type": "STAGE_INTERACTIVE_DONE", "topic": str, "stage": str, "ts": str}
# Written when interactive mode kills the PTY after early AGENT_DONE detection.
```

**Verify:**
```
python -c "from pathly_orchestrator.events import TYPE_STAGE_INTERACTIVE_DONE; print('PASS')"
```

---

### 4.2 `feature_flags.py` — Add `interactive` property

**File:** `src/pathly_orchestrator/feature_flags.py`

**What to add** (after `early_advance`):
```python
@property
def interactive(self) -> bool:
    return self._bool("PATHLY_RUNNER_INTERACTIVE", False)
```

**Verify:**
```
python -c "from pathly_orchestrator.feature_flags import FeatureFlags; assert FeatureFlags().interactive is False; print('PASS')"
```

---

### 4.3 `supervisor.py` — Strip headless flags in interactive mode

**File:** `src/pathly_orchestrator/supervisor.py`

**Where:** In the method that builds the PTY `argv` (wherever `--print` and `--output-format=json` are currently added).

**Logic:**
```python
if not feature_flags.interactive:
    argv += ["--print", "--output-format=json"]
```

Also add a guard at supervisor startup (or at the point `interactive` is first read):
```python
if feature_flags.interactive and not feature_flags.early_advance:
    raise RuntimeError(
        "PATHLY_RUNNER_INTERACTIVE=1 requires PATHLY_RUNNER_EARLY_ADVANCE=1"
    )
```

Emit the RuntimeError message as a `RUNNER_WARNING` SSE before raising so Studio can surface it as a toast.

**Done when:** When `PATHLY_RUNNER_INTERACTIVE=1` is set, the spawned `argv` does NOT contain `--print` or `--output-format=json`. When `PATHLY_RUNNER_INTERACTIVE=1` and `PATHLY_RUNNER_EARLY_ADVANCE` is unset, the supervisor logs a warning and raises.

---

### 4.4 `supervisor.py` — Kill PTY on AGENT_DONE in interactive mode

**File:** `src/pathly_orchestrator/supervisor.py`

**Where:** In the fast-path branch of `_run_stage_via_terminal()`, after `_agent_done_events[run_id]` fires.

**Logic (extend the existing fast-path branch):**
```python
if fired_early == "agent_done":
    _advance_fsm_with_agent_done_data(run_id)
    if feature_flags.interactive:
        # Kill PTY: Studio handles the actual process teardown
        _emit_sse("TERMINAL_KILL", {"tab_id": current_tab_id, "run_id": run_id})
        _write_event(TYPE_STAGE_INTERACTIVE_DONE, {
            "topic": topic,
            "stage": current_stage,
            "ts": _now_iso(),
        })
        _cleanup_run_id(run_id)   # pop all dicts, no reconciliation window
    else:
        _start_reconciliation_window(run_id, timeout=30)
    return
```

**CRITICAL:** `_cleanup_run_id` must pop `_terminal_result_events`, `_terminal_result_data`, `_agent_done_events`, and `_agent_done_stop_events` for `run_id`. Do NOT start a reconciliation window in interactive mode — the PTY was killed, so no billing POST will ever arrive.

**Done when:** Two new tests (see 4.5) pass.

---

### 4.5 `tests/test_supervisor.py` — Two new interactive-mode tests

**Test 1 `test_interactive_mode_kills_pty_on_agent_done`:**
- Set `PATHLY_RUNNER_INTERACTIVE=1` and `PATHLY_RUNNER_EARLY_ADVANCE=1` via monkeypatch.
- Mock `tail_agent_done` to yield one AGENT_DONE immediately.
- Assert `TERMINAL_KILL` SSE was emitted with the correct `tab_id`.
- Assert `TYPE_STAGE_INTERACTIVE_DONE` is written to EVENTS.jsonl.
- Assert no `TYPE_STAGE_RECONCILIATION_FAILURE` is written.
- Assert `_terminal_result_events[run_id]` was cleaned up.

**Test 2 `test_interactive_mode_strips_headless_flags`:**
- Set `PATHLY_RUNNER_INTERACTIVE=1` and `PATHLY_RUNNER_EARLY_ADVANCE=1` via monkeypatch.
- Capture the `argv` passed to the PTY spawn.
- Assert `--print` is NOT in argv.
- Assert `--output-format=json` is NOT in argv.
- Assert `-p` IS in argv (initial prompt still provided).

**Verify:**
```
python -m pytest tests/test_supervisor.py -q
```

---

## Phase 5 — Pipeline History context injection (Conv 5)

> **Depends on:** No hard dependency — can be built independently of Conv 4.
> Touches `runner.py` and `fsm_ops.py`.

### 5.0 Pre-flight

```
python -c "from pathly_orchestrator.runner import read_last_agent_done; print('ok')"
python -c "from pathly_orchestrator.fsm_ops import build_prompt; print('ok')"
python -m pytest tests/ -q
```

All must pass. Do not write any code until pre-flight passes.

---

### 5.1 `runner.py` — Add `build_pipeline_history_block()`

**File:** `src/pathly_orchestrator/runner.py`

**Signature:**
```python
def build_pipeline_history_block(events_path: str, max_items: int = 10) -> str:
```

**Behaviour contract:**
- Returns `""` if `events_path` does not exist or the file has no `AGENT_DONE` lines.
- Reads the full EVENTS.jsonl file (not a tail); collects all events where `type == "AGENT_DONE"`.
- Orders them oldest → newest (file order is already chronological).
- Keeps at most `max_items` entries (drop oldest if more exist).
- Formats each entry as:
  ```
  - **{agent} (conv {conversation})**: {summary}
  ```
  where `agent`, `conversation`, and `summary` come from the AGENT_DONE event dict.
  If `summary` is missing, use `"(no summary)"`. If `conversation` is missing, use `"?"`.
- Returns the full block:
  ```
  \n## Pipeline History\n\n<formatted lines joined by \n>
  ```

**Verify:**
```
python -m pytest tests/test_runner.py -k "pipeline_history" -q
```

---

### 5.2 `tests/test_runner.py` — Two pipeline history tests

**Test 1 `test_pipeline_history_block_format`:**
- Write a temp EVENTS.jsonl with 3 AGENT_DONE entries (agents: builder, reviewer, builder).
- Call `build_pipeline_history_block(path)`.
- Assert the block starts with `\n## Pipeline History\n`.
- Assert exactly 3 formatted lines are present.
- Assert ordering is oldest → newest (matches file order).

**Test 2 `test_pipeline_history_empty_when_no_events`:**
- Call `build_pipeline_history_block` on a nonexistent path.
- Assert the return value is `""` (empty string).
- Call `build_pipeline_history_block` on a file with no AGENT_DONE events.
- Assert the return value is `""`.

---

### 5.3 `fsm_ops.py` — Append Pipeline History in `build_prompt()`

**File:** `src/pathly_orchestrator/fsm_ops.py`

**Where:** In `build_prompt()`, after the call to `_inject_prompt_vars()` returns the final skill text.

**Logic:**
```python
history = build_pipeline_history_block(events_path)
if history:
    prompt_text += history
return prompt_text
```

`events_path` is derived as: `os.path.join(project_root, "pathly", "plans", topic, "EVENTS.jsonl")`.

`build_pipeline_history_block` must be imported from `pathly_orchestrator.runner`.

**IMPORTANT:** The history block is appended AFTER all compose fragments (i.e., after `_inject_prompt_vars`). It is never composed through `compose_skill()` — it is dynamic, generated fresh on each call to `build_prompt()`.

**Done when:** Calling `build_prompt()` for a feature that has prior AGENT_DONE events in EVENTS.jsonl produces a prompt containing `## Pipeline History`.

**Verify:**
```python
python -c "
import os, tempfile, json
from pathly_orchestrator.fsm_ops import build_prompt

# write minimal EVENTS.jsonl
d = tempfile.mkdtemp()
events = os.path.join(d, 'pathly', 'plans', 'test-feature', 'EVENTS.jsonl')
os.makedirs(os.path.dirname(events))
with open(events, 'w') as f:
    f.write(json.dumps({'type':'AGENT_DONE','agent':'builder','conversation':1,'summary':'did stuff','ts':'2026-01-01T00:00:00Z'}) + '\n')

# build_prompt needs skill + topic + project_root + adapter
# replace with a real invocation matching how fsm_ops.build_prompt is called
print('EVENTS.jsonl written to', events)
"
```
Then invoke `build_prompt('team/build', 'test-feature', d, 'claude')` (or the actual signature) and assert `## Pipeline History` is in the output.

---

### 5.4 Final verify (Conv 5)

```
python -m pytest tests/ -q
```

All tests must pass. Append to `pathly/plans/agent-done-early-advance/VERIFY.md`:
- Commands run, outputs, files changed (absolute paths), status PASS or FAIL.

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
