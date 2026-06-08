# CONVERSATION_PROMPTS.md — agent-done-early-advance

---

## Conv 1 — Foundation layer: events, runner tail generator, feature flag

**Stories delivered:** S-1, S-2

Read `FEATURE_INDEX.md` first at `pathly/plans/agent-done-early-advance/FEATURE_INDEX.md`.

### Context

You are implementing the foundation layer for the `agent-done-early-advance` feature.
This conversation touches only the Python layer — no supervisor logic, no TypeScript.

Feature: when an agent writes `AGENT_DONE` to `EVENTS.jsonl` mid-run, the supervisor
will be able to advance the FSM early. This conversation builds the primitives that
make that possible.

### Phase 0 — Pre-flight (mandatory before writing any code)

Run the following and confirm all pass:
```
python -c "from pathly_orchestrator.events import TYPE_AGENT_DONE; print('ok')"
python -c "from pathly_orchestrator.runner import read_last_agent_done; print('ok')"
python -c "from pathly_orchestrator.feature_flags import FeatureFlags; print('ok')"
python -m pytest tests/test_supervisor.py -q
```

Glob-verify these files exist before editing them:
- `src/pathly_orchestrator/events.py`
- `src/pathly_orchestrator/runner.py`
- `src/pathly_orchestrator/feature_flags.py`

Do not write any code until Phase 0 passes.

### Phase 1 — `events.py`: add reconciliation failure constant

In `src/pathly_orchestrator/events.py`, after the last existing `TYPE_` constant, add:

```python
TYPE_STAGE_RECONCILIATION_FAILURE = "STAGE_RECONCILIATION_FAILURE"
# Schema: {"type": "STAGE_RECONCILIATION_FAILURE", "topic": str, "stage": str,
#           "exit_code": int, "ts": str (ISO-8601)}
# Written when a PTY billing POST does not arrive within the reconciliation
# window after an early FSM advance.
```

Verify:
```
python -c "from pathly_orchestrator.events import TYPE_STAGE_RECONCILIATION_FAILURE; assert TYPE_STAGE_RECONCILIATION_FAILURE == 'STAGE_RECONCILIATION_FAILURE'; print('PASS')"
```

### Phase 2 — `feature_flags.py`: add `early_advance` property

In `src/pathly_orchestrator/feature_flags.py`, add to the `FeatureFlags` class using
the existing `_bool()` helper pattern:

```python
@property
def early_advance(self) -> bool:
    return self._bool("PATHLY_RUNNER_EARLY_ADVANCE", False)
```

Verify (run both):
```
python -c "from pathly_orchestrator.feature_flags import FeatureFlags; assert FeatureFlags().early_advance is False; print('PASS')"
```
```
PATHLY_RUNNER_EARLY_ADVANCE=1 python -c "from pathly_orchestrator.feature_flags import FeatureFlags; assert FeatureFlags().early_advance is True; print('PASS')"
```

### Phase 3 — `runner.py`: add `tail_agent_done()` generator

In `src/pathly_orchestrator/runner.py`, add the following generator function.
Place it after `read_last_agent_done()`:

```python
def tail_agent_done(
    path: str,
    after_ts: str,
    stop_evt: threading.Event,
    poll_interval: float = 0.1,
) -> Generator[dict, None, None]:
    """
    Tail EVENTS.jsonl and yield AGENT_DONE events with ts >= after_ts.
    Tracks byte offset so no event is yielded twice.
    Stops when stop_evt is set and no new bytes remain.
    Does not raise if the file does not exist yet — waits until it does.
    """
```

Behaviour requirements:
- Open file in binary append+read mode; track byte offset between polls.
- On each poll: seek to offset, read new bytes, split on `\n`, parse JSON lines.
- Yield a dict if `event["type"] == "AGENT_DONE"` and `event.get("ts","") >= after_ts`.
- Sleep `poll_interval` between polls.
- Return (stop iterating) when `stop_evt.is_set()` and last poll produced no new bytes.
- Skip blank lines and JSON parse errors silently.

### Phase 4 — Unit test for `tail_agent_done`

In `tests/test_runner.py` (create if it does not exist), add a test named
`test_tail_agent_done_yields_and_stops`:

1. Write a temp EVENTS.jsonl with one `BUILD_START` event (should not be yielded).
2. Start `tail_agent_done` in a thread; collect results into a list.
3. Append an `AGENT_DONE` event to the file from the main thread.
4. Wait up to 2 seconds for the result list to be non-empty.
5. Set `stop_evt`; join the thread.
6. Assert exactly one dict was yielded and its `type == "AGENT_DONE"`.

Verify:
```
python -m pytest tests/test_runner.py -k "tail_agent_done" -q
```

### Phase 5 — Final verify

Run the full test suite:
```
python -m pytest tests/ -q
```
All tests must pass. Then write `pathly/plans/agent-done-early-advance/VERIFY.md`
with:
- The exact commands you ran in this conversation.
- The output of each verify command (pass/fail).
- Any files changed (absolute paths).
- Status: PASS or FAIL.

---

## Conv 2 — Supervisor watcher, reconciliation window, and tests

**Stories delivered:** S-3, S-4, S-5, S-6

Read `FEATURE_INDEX.md` first at `pathly/plans/agent-done-early-advance/FEATURE_INDEX.md`.

### Context

Conv 1 must be DONE before starting this conversation (check PROGRESS.md).

This conversation wires the fast-path advance into `supervisor.py`:
- A watcher thread reads EVENTS.jsonl using `tail_agent_done`.
- When AGENT_DONE is detected, the supervisor advances the FSM immediately.
- The PTY path stays alive for billing reconciliation (30-second window).
- If billing never arrives, `STAGE_RECONCILIATION_FAILURE` is written.
- When the feature flag is off, nothing changes.

### Phase 0 — Pre-flight

```
python -c "from pathly_orchestrator.events import TYPE_STAGE_RECONCILIATION_FAILURE; print('ok')"
python -c "from pathly_orchestrator.runner import tail_agent_done; print('ok')"
python -c "from pathly_orchestrator.feature_flags import FeatureFlags; assert FeatureFlags().early_advance is False; print('ok')"
python -m pytest tests/ -q
```

All must pass. Do not write any code until Phase 0 passes.

### Phase 1 — Supervisor state: add `_agent_done_events` dict

In `src/pathly_orchestrator/supervisor.py`, in the `Supervisor.__init__` (or wherever
`_terminal_result_events` is initialised), add:

```python
self._agent_done_events: dict[str, threading.Event] = {}
self._agent_done_stop_events: dict[str, threading.Event] = {}
```

CRITICAL: these dicts are independent signal channels. The watcher code MUST NEVER
read from or write to `_terminal_result_events` or `_terminal_result_data`.

### Phase 2 — Watcher thread method

Add `_agent_done_watcher(self, run_id, events_path, start_ts)` to the supervisor.
It calls `tail_agent_done(events_path, start_ts, stop_evt)` and sets
`self._agent_done_events[run_id]` on first yield, then returns.

The watcher is started as a daemon thread in `_run_stage_via_terminal()` when
`feature_flags.early_advance` is True, before the wait begins.

### Phase 3 — Fast-path branch in `_run_stage_via_terminal()`

After starting the watcher thread (when `early_advance` is True), implement a race
between `_agent_done_events[run_id]` and `result_evt`:

- Use `threading.Event.wait(timeout=…)` in a short loop or `concurrent.futures` to
  race the two events without busy-waiting.
- If `_agent_done_events[run_id]` fires first: advance FSM using AGENT_DONE data
  from EVENTS.jsonl (use `read_last_agent_done()`), then start the reconciliation
  window thread (see Phase 4), then return from `_run_stage_via_terminal()`.
- If `result_evt` fires first (slow path): cancel the watcher (set stop_evt),
  continue with existing logic.
- If timeout (1800 s): cancel watcher, continue with existing timeout logic.

### Phase 4 — Reconciliation window thread

Add `_reconciliation_window(self, run_id, stage, timeout=30)`:
1. Call `self._terminal_result_events[run_id].wait(timeout=timeout)`.
2. If arrived (True): read `_terminal_result_data[run_id]` for `cost_usd` and
   `session_id`; write a billing update event to EVENTS.jsonl. Do NOT call FSM advance.
3. If not arrived (False): write `TYPE_STAGE_RECONCILIATION_FAILURE` event with
   `exit_code=-1`.
4. Clean up: pop `_terminal_result_events[run_id]`, `_terminal_result_data[run_id]`,
   `_agent_done_events[run_id]`, `_agent_done_stop_events[run_id]`.

### Phase 5 — `/runner/terminal/result` handler guard

In `http_server.py` (or wherever the POST handler lives), verify: the handler must
return 200 (not 404) even when early advance has already occurred, as long as the
reconciliation window is still open. The handler only needs to write the data and
set the event — it does not know whether early advance happened.

Confirm this is already guaranteed by the separate dict design (the handler checks
`_terminal_result_events`, which was never removed by the watcher). If a code change
is needed, make it; if not, add a comment explaining the invariant.

### Phase 6 — Three new tests in `test_supervisor.py`

Use the `test_abort_stops_run` threading pattern as a template.

**Test 1 `test_early_advance_with_billing_reconciliation`:**
- Set `PATHLY_RUNNER_EARLY_ADVANCE=1` via monkeypatch.
- Mock `tail_agent_done` to yield one AGENT_DONE immediately.
- Mock `_terminal_result_events[run_id].wait` to return True (billing arrives).
- Assert FSM advance called once.
- Assert `TYPE_STAGE_RECONCILIATION_FAILURE` NOT in EVENTS.jsonl.

**Test 2 `test_early_advance_billing_timeout`:**
- Set `PATHLY_RUNNER_EARLY_ADVANCE=1` via monkeypatch.
- Mock reconciliation window timeout = 0.1 s; PTY POST never arrives.
- Assert FSM advance called once.
- Assert `TYPE_STAGE_RECONCILIATION_FAILURE` IS in EVENTS.jsonl.

**Test 3 `test_slow_path_no_regression`:**
- Do not set `PATHLY_RUNNER_EARLY_ADVANCE`.
- Mock PTY POST arriving normally.
- Assert FSM advance called once.
- Assert `_agent_done_events` dict was never written.

### Phase 7 — Final verify

```
python -m pytest tests/ -q
```

All tests pass. Then write `pathly/plans/agent-done-early-advance/VERIFY.md`
(append to it if Conv 1 already wrote it) with:
- Commands run, outputs, files changed (absolute paths), status PASS or FAIL.

---

## Conv 3 — Studio SSE pill (optional, cosmetic)

**Stories delivered:** cosmetic only — no story gate

Read `FEATURE_INDEX.md` first at `pathly/plans/agent-done-early-advance/FEATURE_INDEX.md`.

### Context

This conversation is independent of Conv 1 and Conv 2. It adds a UI status
indicator so the user sees "finalizing..." on a stage tile when the watcher fires
early, rather than seeing the stage appear to still be running.

No changes to PTY spawn, PTY exit handler, or the `/runner/terminal/result` POST
logic. Scope is strictly limited to emitting an SSE event.

### Phase 0 — Pre-flight

```
cd studio && npx tsc --noEmit
```

Must exit 0 before any changes.

### Phase 1 — Emit `TERMINAL_AGENT_DONE` SSE

In `studio/src/main/ipc/terminal.ts`, when the Python supervisor emits a
`TERMINAL_AGENT_DONE` SSE (via the existing SSE channel), forward it to the
renderer. The renderer should update the stage status pill to "finalizing...".

Implementation note: follow the existing SSE forwarding pattern used for
`TERMINAL_SPAWN` — do not invent a new IPC channel.

### Phase 2 — Final verify

```
cd studio && npx tsc --noEmit
```

Then write `pathly/plans/agent-done-early-advance/VERIFY.md` (append) with:
- Commands run, outputs, files changed (absolute paths), status PASS or FAIL.

---

## Conv 4 — Interactive mode: visible PTY, kill on AGENT_DONE

**Stories delivered:** S-7

Read `FEATURE_INDEX.md` first at `pathly/plans/agent-done-early-advance/FEATURE_INDEX.md`.

### Context

Conv 2 must be DONE before starting this conversation (check PROGRESS.md).

This conversation adds interactive mode: when `PATHLY_RUNNER_INTERACTIVE=1`, agents run
in a visible, non-headless PTY. The `--print` and `--output-format=json` flags are stripped
from the spawn argv so Claude Code runs interactively. When the watcher (built in Conv 2)
detects AGENT_DONE in EVENTS.jsonl, the supervisor emits a `TERMINAL_KILL` SSE — Studio
closes the tab — rather than waiting for a natural PTY exit.

Interactive mode requires early advance (`PATHLY_RUNNER_EARLY_ADVANCE=1`); the supervisor
raises a `RuntimeError` (surfaced as `RUNNER_WARNING` SSE) if the combination is invalid.

### Phase 0 — Pre-flight (mandatory before writing any code)

Run the following and confirm all pass:
```
python -c "from pathly_orchestrator.events import TYPE_STAGE_RECONCILIATION_FAILURE; print('ok')"
python -c "from pathly_orchestrator.runner import tail_agent_done; print('ok')"
python -c "from pathly_orchestrator.feature_flags import FeatureFlags; assert FeatureFlags().early_advance is False; print('ok')"
python -m pytest tests/test_supervisor.py -q
```

Do not write any code until Phase 0 passes.

### Phase 1 — `events.py`: add `STAGE_INTERACTIVE_DONE` constant

In `src/pathly_orchestrator/events.py`, after `TYPE_STAGE_RECONCILIATION_FAILURE`, add:

```python
TYPE_STAGE_INTERACTIVE_DONE = "STAGE_INTERACTIVE_DONE"
# Schema: {"type": "STAGE_INTERACTIVE_DONE", "topic": str, "stage": str, "ts": str}
# Written when interactive mode kills the PTY after early AGENT_DONE detection.
```

Verify:
```
python -c "from pathly_orchestrator.events import TYPE_STAGE_INTERACTIVE_DONE; print('PASS')"
```

### Phase 2 — `feature_flags.py`: add `interactive` property

In `src/pathly_orchestrator/feature_flags.py`, add to the `FeatureFlags` class after `early_advance`:

```python
@property
def interactive(self) -> bool:
    return self._bool("PATHLY_RUNNER_INTERACTIVE", False)
```

Verify:
```
python -c "from pathly_orchestrator.feature_flags import FeatureFlags; assert FeatureFlags().interactive is False; print('PASS')"
```

### Phase 3 — `supervisor.py`: strip headless flags in interactive mode

Find the method that builds the PTY `argv` (the one that currently appends `--print`
and `--output-format=json`). Wrap those two flags in a guard:

```python
if not feature_flags.interactive:
    argv += ["--print", "--output-format=json"]
```

Also add a startup guard wherever `feature_flags` is first read in the run path:

```python
if feature_flags.interactive and not feature_flags.early_advance:
    msg = "PATHLY_RUNNER_INTERACTIVE=1 requires PATHLY_RUNNER_EARLY_ADVANCE=1"
    _emit_sse("RUNNER_WARNING", {"message": msg})
    raise RuntimeError(msg)
```

Do NOT change any other argv items — `-p <prompt>`, `--model`, `--dangerously-skip-permissions`
must remain regardless of mode.

### Phase 4 — `supervisor.py`: kill PTY on AGENT_DONE in interactive mode

In the fast-path branch of `_run_stage_via_terminal()` (the block that fires when
`_agent_done_events[run_id]` wins the race), extend the existing logic:

```python
if fired_early == "agent_done":
    _advance_fsm_with_agent_done_data(run_id)
    if feature_flags.interactive:
        _emit_sse("TERMINAL_KILL", {"tab_id": current_tab_id, "run_id": run_id})
        _write_event(TYPE_STAGE_INTERACTIVE_DONE, {
            "topic": topic,
            "stage": current_stage,
            "ts": _now_iso(),
        })
        _cleanup_run_id(run_id)   # pops all four dicts; no reconciliation window
    else:
        _start_reconciliation_window(run_id, timeout=30)
    return
```

`_cleanup_run_id` must pop: `_terminal_result_events`, `_terminal_result_data`,
`_agent_done_events`, `_agent_done_stop_events` for `run_id`. No reconciliation window
in interactive mode — the PTY was killed, so no billing POST will ever arrive.

### Phase 5 — `test_supervisor.py`: two new interactive-mode tests

**Test 1 `test_interactive_mode_kills_pty_on_agent_done`:**
- Monkeypatch `PATHLY_RUNNER_INTERACTIVE=1` and `PATHLY_RUNNER_EARLY_ADVANCE=1`.
- Mock `tail_agent_done` to yield one AGENT_DONE immediately.
- Assert `TERMINAL_KILL` SSE was emitted with the correct `tab_id`.
- Assert `TYPE_STAGE_INTERACTIVE_DONE` is written to EVENTS.jsonl.
- Assert `TYPE_STAGE_RECONCILIATION_FAILURE` is NOT written.
- Assert `_terminal_result_events[run_id]` is absent after the call.

**Test 2 `test_interactive_mode_strips_headless_flags`:**
- Monkeypatch `PATHLY_RUNNER_INTERACTIVE=1` and `PATHLY_RUNNER_EARLY_ADVANCE=1`.
- Capture the `argv` passed to the PTY spawn.
- Assert `"--print"` is NOT in argv.
- Assert `"--output-format=json"` is NOT in argv.
- Assert `"-p"` IS in argv.

### Phase 6 — Final verify

```
python -m pytest tests/ -q
```

All tests must pass. Append to `pathly/plans/agent-done-early-advance/VERIFY.md`:
- Commands run, outputs, files changed (absolute paths), status PASS or FAIL.

---

## Conv 5 — Pipeline History context injection

**Stories delivered:** S-8

Read `FEATURE_INDEX.md` first at `pathly/plans/agent-done-early-advance/FEATURE_INDEX.md`.

### Context

This conversation is independent of Conv 4. It can be built any time after Conv 1.

Every stage prompt currently lacks awareness of what previous agents accomplished.
This conversation adds a `## Pipeline History` block — generated from EVENTS.jsonl
AGENT_DONE entries — appended to every prompt returned by `build_prompt()` in
`fsm_ops.py`. Agents receive a compact summary of prior work without needing to re-read
all plan files.

### Phase 0 — Pre-flight

```
python -c "from pathly_orchestrator.runner import read_last_agent_done; print('ok')"
python -c "from pathly_orchestrator.fsm_ops import build_prompt; print('ok')"
python -m pytest tests/ -q
```

All must pass. Do not write any code until Phase 0 passes.

Also read `src/pathly_orchestrator/fsm_ops.py` (specifically `build_prompt()`) to
understand where the history block must be appended.

### Phase 1 — `runner.py`: add `build_pipeline_history_block()`

In `src/pathly_orchestrator/runner.py`, add the following function.
Place it after `tail_agent_done()`:

```python
def build_pipeline_history_block(events_path: str, max_items: int = 10) -> str:
    """
    Return a markdown ## Pipeline History block from AGENT_DONE events in
    events_path. Returns "" if the file is absent or has no AGENT_DONE lines.
    Entries are ordered oldest-first; at most max_items are included.
    """
```

Behaviour requirements:
- Returns `""` if `events_path` does not exist.
- Reads the whole file; collects lines where `type == "AGENT_DONE"`.
- Orders oldest → newest (file order is chronological).
- Keeps the last `max_items` entries; drop older ones if count exceeds the limit.
- Formats each entry as: `- **{agent} (conv {conversation})**: {summary}`
  — use `"?"` if `conversation` is missing, `"(no summary)"` if `summary` is missing.
- Returns:
  ```
  \n## Pipeline History\n\n<entry1>\n<entry2>\n...
  ```
- Skip blank lines and JSON parse errors silently.

### Phase 2 — Unit tests for `build_pipeline_history_block`

In `tests/test_runner.py`, add:

**`test_pipeline_history_block_format`:**
1. Write a temp EVENTS.jsonl with 3 AGENT_DONE entries:
   - builder, conv 1, summary "added event constant"
   - reviewer, conv 1, summary "review PASS"
   - builder, conv 2, summary "wired supervisor"
2. Call `build_pipeline_history_block(path)`.
3. Assert the block starts with `"\n## Pipeline History\n"`.
4. Assert all 3 formatted lines are present in order.
5. Assert line format matches `"- **builder (conv 1)**: added event constant"` etc.

**`test_pipeline_history_empty_when_no_events`:**
1. Call `build_pipeline_history_block` on a nonexistent path — assert `""`.
2. Write a temp EVENTS.jsonl with only non-AGENT_DONE lines — assert `""`.

Verify:
```
python -m pytest tests/test_runner.py -k "pipeline_history" -q
```

### Phase 3 — `fsm_ops.py`: append history in `build_prompt()`

In `src/pathly_orchestrator/fsm_ops.py`:

1. Import `build_pipeline_history_block` from `pathly_orchestrator.runner`.
2. Derive `events_path`:
   ```python
   events_path = os.path.join(project_root, "pathly", "plans", topic, "EVENTS.jsonl")
   ```
3. At the end of `build_prompt()`, after `_inject_prompt_vars()` returns the final text:
   ```python
   history = build_pipeline_history_block(events_path)
   if history:
       prompt_text += history
   return prompt_text
   ```

The history block must be appended AFTER all compose fragments (after `_inject_prompt_vars`).
It is never composed through `compose_skill()` — it is generated fresh on every call.

**Done when:** A call to `build_prompt()` for a feature that has prior AGENT_DONE events
produces a string containing `"## Pipeline History"`.

### Phase 4 — Smoke test for `build_prompt()` + history injection

Write a quick inline smoke test (as part of `tests/test_fsm_ops.py` or append to
`test_runner.py`) named `test_build_prompt_includes_pipeline_history`:

1. Create a temp project root with `pathly/plans/test-feature/EVENTS.jsonl` containing
   one AGENT_DONE entry (builder, conv 1, summary "smoke test entry").
2. Call `build_prompt(skill="team/build", topic="test-feature", project_root=tmp_root, adapter="claude")`.
3. Assert the returned string contains `"## Pipeline History"`.
4. Assert the returned string contains `"smoke test entry"`.

Verify:
```
python -m pytest tests/ -k "pipeline_history" -q
```

### Phase 5 — Final verify

```
python -m pytest tests/ -q
```

All tests must pass. Append to `pathly/plans/agent-done-early-advance/VERIFY.md`:
- Commands run, outputs, files changed (absolute paths), status PASS or FAIL.
