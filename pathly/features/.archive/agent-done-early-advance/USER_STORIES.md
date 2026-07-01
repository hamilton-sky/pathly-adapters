# USER_STORIES.md — agent-done-early-advance

## S-1 — AGENT_DONE event constant and schema

**As a** developer reading the event log,
**I want** a canonical `TYPE_STAGE_RECONCILIATION_FAILURE` constant and inline schema comment in `events.py`,
**so that** every writer and reader uses the same string and I never need to grep for the literal.

### Acceptance criteria
- `events.py` exports `TYPE_STAGE_RECONCILIATION_FAILURE = "STAGE_RECONCILIATION_FAILURE"`.
- A schema comment immediately below the constant documents all required fields:
  `type`, `topic`, `stage`, `exit_code`, `ts`.
- `python -c "from pathly_orchestrator.events import TYPE_STAGE_RECONCILIATION_FAILURE; assert TYPE_STAGE_RECONCILIATION_FAILURE == 'STAGE_RECONCILIATION_FAILURE'"` exits 0.
- No existing constants are renamed or removed.

**Delivered by:** Conv 1

---

## S-2 — Tail generator for AGENT_DONE events

**As a** supervisor thread,
**I want** a `tail_agent_done(path, after_ts, stop_evt, poll_interval)` generator that tails EVENTS.jsonl and yields new `AGENT_DONE` dicts,
**so that** the watcher thread can react to an agent writing AGENT_DONE without reading the whole file on every poll.

### Acceptance criteria
- `tail_agent_done` is importable from `pathly_orchestrator.runner`.
- It yields only events where `type == "AGENT_DONE"` and `ts >= after_ts`.
- It stops yielding when `stop_evt.is_set()` and the file has no more new lines.
- It does not re-yield events already seen (tracks byte offset internally).
- A unit test with a temp file that has events appended mid-poll passes.
- Poll interval defaults to 0.1 s; caller may override.
- `feature_flags.early_advance` is `False` by default (env var `PATHLY_RUNNER_EARLY_ADVANCE` unset).
- `feature_flags.early_advance` returns `True` when `PATHLY_RUNNER_EARLY_ADVANCE=1` is set.

**Delivered by:** Conv 1

---

## S-3 — Early FSM advance on AGENT_DONE detection

**As a** user watching the Studio pipeline,
**I want** the FSM to advance to the next stage as soon as the agent writes AGENT_DONE to EVENTS.jsonl,
**so that** the next stage starts without waiting for the PTY process to exit.

### Acceptance criteria
- When `PATHLY_RUNNER_EARLY_ADVANCE=1` and an `AGENT_DONE` event appears in EVENTS.jsonl, the supervisor calls the FSM advance within 1 second of the event being written.
- The PTY process is NOT killed — it continues running until it exits naturally.
- The existing `/runner/terminal/result` POST path continues to accept the PTY's billing POST after early advance — a 404 is never returned to the PTY POST caller.
- The FSM advances exactly once per stage even if multiple AGENT_DONE events are written.
- When `PATHLY_RUNNER_EARLY_ADVANCE` is unset or `0`, behaviour is identical to the current code (no regression).

**Delivered by:** Conv 2

---

## S-4 — Billing reconciliation after early advance

**As a** pipeline operator reviewing costs,
**I want** the cost_usd and session_id from the PTY's billing POST to be recorded even after early advance,
**so that** I never lose billing data because the FSM moved on before the PTY exited.

### Acceptance criteria
- After early advance, `_terminal_result_events[run_id]` remains in the dict for at least 30 seconds.
- When the billing POST arrives within the reconciliation window, `cost_usd` and `session_id` are written to the feature's EVENTS.jsonl (or equivalent store) without re-triggering FSM advance.
- If the billing POST does not arrive within 30 seconds, a `STAGE_RECONCILIATION_FAILURE` event is written to EVENTS.jsonl.
- The `STAGE_RECONCILIATION_FAILURE` event contains: `type`, `topic`, `stage`, `exit_code` (from PTY, or -1 if never received), `ts`.
- After the reconciliation window closes (success or timeout), `_terminal_result_events[run_id]` is removed.

**Delivered by:** Conv 2

---

## S-5 — No-early-advance regression

**As a** pipeline operator,
**I want** the existing slow path (wait for PTY exit) to work exactly as before when the feature flag is off,
**so that** enabling the feature is a safe, reversible opt-in.

### Acceptance criteria
- With `PATHLY_RUNNER_EARLY_ADVANCE` unset, all existing `test_supervisor.py` tests pass without modification.
- The PTY POST `/runner/terminal/result` always returns 200 regardless of flag state.
- No new dict keys or thread objects are created in the supervisor when the flag is off.

**Delivered by:** Conv 2

---

## S-6 — Watcher test coverage

**As a** developer,
**I want** three new tests in `test_supervisor.py` covering the watcher scenarios,
**so that** no regression can merge silently.

### Acceptance criteria

Test 1 — Fast path: watcher fires, PTY POST arrives within window.
- FSM advance is called exactly once.
- Billing fields are updated from the PTY POST.
- No `STAGE_RECONCILIATION_FAILURE` event is written.

Test 2 — Timeout path: watcher fires, PTY POST never arrives.
- FSM advance is called exactly once.
- A `STAGE_RECONCILIATION_FAILURE` event is written.
- `_terminal_result_events[run_id]` is cleaned up after the window.

Test 3 — Slow path (no regression): watcher is inactive (flag off), PTY exits normally.
- FSM advance is called exactly once via the existing path.
- No watcher thread is started.

All three tests use `patch` / `threading.Event` mocks consistent with the existing `test_abort_stops_run` pattern.

**Delivered by:** Conv 2

---

## S-7 — Interactive mode: visible PTY, kill on AGENT_DONE

**As a** developer using Studio,
**I want** agents to run in an interactive (non-headless) PTY when `PATHLY_RUNNER_INTERACTIVE=1`,
**so that** I can watch the Claude Code session live, interact if needed, and have the terminal
close automatically once the agent signals it is done.

### Acceptance criteria
- `FeatureFlags().interactive` returns `False` by default and `True` when `PATHLY_RUNNER_INTERACTIVE=1` is set.
- `interactive=True` implies `early_advance=True`; the supervisor raises `RuntimeError` (logged + surfaced as `RUNNER_WARNING` SSE) if interactive is True but early_advance is False.
- When `interactive=True`, the PTY argv built by the supervisor does **not** include `--print` or `--output-format=json`; all other flags (`-p <prompt>`, `--model`, `--dangerously-skip-permissions`) remain unchanged.
- When `_agent_done_events[run_id]` fires in interactive mode, the supervisor emits a `TERMINAL_KILL` SSE event carrying the `tab_id`; Studio closes the PTY tab.
- After PTY kill: no reconciliation window is started; a `STAGE_INTERACTIVE_DONE` event is written to EVENTS.jsonl (`type`, `topic`, `stage`, `ts`).
- When `interactive=False` (default), all existing behavior from Conv 2 is unchanged.
- `python -m pytest tests/test_supervisor.py -q` — all tests pass (new + existing).

**Delivered by:** Conv 4

---

## S-8 — Pipeline History context block injected into every stage prompt

**As an** agent receiving a stage prompt,
**I want** a `## Pipeline History` section at the bottom of my instructions listing what
previous agents accomplished,
**so that** I have the full context of prior work without needing to re-read all plan files.

### Acceptance criteria
- `build_pipeline_history_block(events_path, max_items=10)` is importable from `pathly_orchestrator.runner`.
- Returns an empty string when EVENTS.jsonl does not exist or contains no AGENT_DONE events.
- When AGENT_DONE events exist, returns a block starting with `\n## Pipeline History\n`.
- Each line follows the format: `- **{agent} (conv {conversation})**: {summary}` — one entry per AGENT_DONE, ordered oldest → newest.
- At most `max_items` entries are included; if more exist, the oldest are dropped.
- `build_prompt()` in `fsm_ops.py` appends the pipeline history block to the composed skill text before returning; if the block is empty, nothing is appended.
- `python -m pytest tests/test_runner.py -k "pipeline_history" -q` passes.

**Delivered by:** Conv 5
