# A retried run keeps its goal, its board and its interactive mode

Type: task
Status: resolved
Blocked by: 12
Test first: yes
Level: 2
Touches: src/pathly_orchestrator/http_server/blueprints/control/_helpers.py, src/pathly_orchestrator/http_server/blueprints/runner/api_control.py, tests/http_api/test_retry_keeps_goal_and_board.py (new), src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/http_api/INDEX.md

Carried from HANDOFF 19 (cleanup round after round two; the person said yes on 2026-11-08). Both
retry routes rebuild a run from the request body alone:

- `POST /runs/<id>/retry` (`control/_helpers.handle_retry`, which receives the ended run's
  `RunnerState` as `state`), and
- `POST /runner/retry` (`runner/api_control.runner_retry`, which reads it with
  `supervisor.get_state(topic)`).

Neither passes `goal_id`, `board` or `interactive` to `supervisor.api.start_run`, so a retried
goal run loses its goal (its terminal planner is no longer told to seed that goal's DAG), a
retried `goal-loop` run on the project board gets `feature` spawn tokens (its tasks' role
questions then go to the person, the bug ticket 19 fixed for resume), and a headless run comes
back interactive. `resume_parked_run` (`src/pathly_orchestrator/supervisor/api.py`) already carries all three from the
prior state: do the same here. When the prior state is there, pass `goal_id=state.goal_id`,
`board=state.scope_tier` and `interactive=state.interactive`; `/runner/retry` with no prior
state keeps today's defaults. The body still decides flow, project root, model, timeout, caps and
autonomy, as today.

Both routes also drop the ended run's registry entry (`_registry.pop(topic, None)`) BEFORE they
validate the body, so a retry with a bad body (400) loses the run: a second, correct retry of the
same `run_id` then answers `not_active`. Validate first, and drop the entry only once the body is
valid (`start_run` replaces the entry anyway).

Update the sentence in `src/pathly_orchestrator/CLAUDE.md` that says the control-plane retry
"starts with the default `feature`".

## Not in this ticket

- Carrying the prior run's flow, project root, model or caps when the body omits them (the
  body's required fields stay required).
- `goal_executor` choosing the tier by flow name (`goal-loop`) rather than by fan-out.

## Done when

- `python -m pytest tests/http_api/test_retry_keeps_goal_and_board.py -q -p no:cacheprovider`
  passes and covers, with `start_run` patched to record its keyword arguments: `POST
  /runs/<id>/retry` of an ended run with `goal_id` `g-1`, `scope_tier` `project` and
  `interactive` False calls `start_run` with `goal_id="g-1"`, `board="project"`,
  `interactive=False`; `POST /runner/retry` for the same kind of ended run does the same; and for
  each route, a retry with a missing required field answers 400 and leaves the ended run in the
  registry, so a following valid retry of it reaches `start_run`.
- The existing retry tests (`tests/http_api/test_runs_control.py`,
  `tests/http_api/test_run_cost_values.py`, `tests/http_api/test_chief_budget_edges.py`) still
  pass, and `python scripts/gen_test_index.py --check` passes.

```check
$ python -m pytest tests/http_api/test_retry_keeps_goal_and_board.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/http_api -q -p no:cacheprovider
exit 0
$ python scripts/gen_test_index.py --check
exit 0
```

## Reference

- `src/pathly_orchestrator/supervisor/api.py` `resume_parked_run` (what it carries) and `start_run` (`board` ->
  `scope_tier_for(board)`).
- HANDOFF 19 in `/mnt/project-files/chief-autopilot-round-two/handoffs.md` (minors carried).

## Answer

Work started at `aca614d4af3d5e52fa0497c89409c5d54b18029b`; test-only commit `c8accaa`.

- **Built**: `control/_helpers.py` (`handle_retry`), `runner/api_control.py` (`runner_retry`),
  new `tests/http_api/test_retry_keeps_goal_and_board.py` (5 tests), `src/pathly_orchestrator/CLAUDE.md`
  (the scope_tier sentence), `tests/INDEX.md` and `tests/http_api/INDEX.md` (regenerated).
- **Proof**:
  - `python -m pytest tests/http_api/test_retry_keeps_goal_and_board.py -q -p no:cacheprovider`:
    `5 passed`, exit 0 (at the test-only commit: 4 failed, `KeyError: 'goal_id'` and the run gone
    from the registry after the 400). Covers both routes: `start_run` gets `goal_id="g-1"`,
    `board="project"`, `interactive=False`; a body missing `max_cost_usd` answers 400, starts
    nothing, leaves the run in `_registry`, and the following valid retry reaches `start_run`;
    plus `/runner/retry` with no prior state passes none of the three (defaults stand).
  - `tests/http_api/test_runs_control.py`, `test_run_cost_values.py`, `test_chief_budget_edges.py`
    together with the new file: `259 passed`.
  - `python -m pytest tests/http_api -q -p no:cacheprovider`: `4 failed, 2615 passed` (exit 1).
    The 4 (`test_chief_routes.py::test_main_closes_a_session_the_last_process_left_open_before_serving`,
    `::test_main_still_serves_when_the_chief_cleanup_fails`,
    `test_chief_startup_port.py::test_main_leaves_a_chief_open_when_something_already_answers_on_its_port`,
    `::test_main_closes_the_sessions_when_nothing_answers_on_its_port`) fail identically at the
    base commit with my changes stashed (4 failed, 74 passed): their subprocess sets `HOME` to a
    temp dir, and in this container `markupsafe` lives only in the user site of the real home, so
    `import flask` fails ("Flask not installed"). Environment, not this ticket; left alone.
  - `python scripts/gen_test_index.py --check`: "All test INDEX.md files up to date.", exit 0.
  - Also: black, mypy (blueprints), `check_file_size.py` (none new, none grown; files at 335 and
    347 lines), `lint-imports` all clean.
- **Decisions**: the registry pop moved below all body validation (kept, not dropped, so the
  ended entry is gone before `start_run` as before). `handle_retry` reads the three fields with
  `getattr` and `RunnerState`'s defaults, because `tests/http_api/chief_budget_support.py` puts a
  `SimpleNamespace` (no `interactive`/`goal_id`/`scope_tier`) in the registry and that support
  file is outside Touches; with plain attribute access 7 budget-edge tests answered 500.
  `runner_retry` passes the three only when `state is not None` (`**carried`).
- **Shortcuts taken**: none.
- **For later tickets**: none affected.
