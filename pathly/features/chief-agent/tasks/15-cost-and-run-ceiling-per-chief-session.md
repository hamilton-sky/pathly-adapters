# Cap what one chief session can spend and start

Type: task
Status: resolved
Blocked by: 08
Test first: yes

Nothing limits an Operator chief today. `POST /runs` accepts any positive `max_cost_usd`
(`blueprints/control/_helpers.py`, the `max_cost_usd` check), and a chief can start runs in a loop.
A prompt-injected or confused chief could spend without bound while the user is away.

Add two per-machine settings, read with `db/queries/app_settings.get_setting` and set by the user
with `PUT /db/settings` (which the chief gate already refuses for chief tokens):

- `chief.max_cost_usd_per_run`, default `10.0`: a chief-token `POST /runs` whose `max_cost_usd`
  is above it gets 403 `{"error": "max_cost_usd above this chief's ceiling", "ceiling": …}`.
- `chief.max_runs_per_session`, default `20`: every `run` call that starts work (`POST /runs`,
  `/comms/goals/run`, `/comms/run`, `/comms/tasks/run`) counts one. Past the limit the gate
  answers 403 `{"error": "this chief session has started its maximum number of runs", "limit":
  …}`. The decompose routes (`plan`) do not count. The user raises the limit or opens a new chief.

Count in a new column `chief_sessions.runs_started INTEGER NOT NULL DEFAULT 0` (additive, added by
`migrations_chief.add_chief_tables`). Increment it with a conditional `UPDATE ... SET runs_started
= runs_started + 1 WHERE run_id = ? AND runs_started < ?` under `_get_write_lock` and refuse when
no row changed, so two concurrent calls cannot both take the last slot. The count is taken when
the gate allows the call, so two racing starts cannot both get past it. When the route then
answers with a 4xx (bad body, unknown goal, no ready task: nothing was started, nothing spent),
the slot is given back: the gate sets `flask.g.chief_run_slot = run_id`, and an `after_request`
function registered with the gate runs `UPDATE ... SET runs_started = runs_started - 1 WHERE
run_id = ? AND runs_started > 0` for a response with status 400 to 499. A 2xx keeps the slot, even
if the run fails later (it may already have spent), and so does a 5xx (fail closed: the server
cannot tell whether work started). Without the refund, a chief whose start calls keep failing
validation would use up its limit on calls that started nothing. Put the check and the refund in
their own module (for example `http_server/chief_budget.py`), called from `chief_gate` after the
action and project checks.

`GET /chief/session` gains `runs_started`, `max_runs_per_session` and `max_cost_usd_per_run`, so
the chief can tell the user why it stopped.

Living docs: the two settings in the "Chief gate" paragraph of `src/pathly_orchestrator/CLAUDE.md`.

## Not in this ticket

- The chief's own token cost: round two bills the chief session (map.md § Round two).
- A running-cost ceiling summed across the session's runs: needs the round-two billing first.

## Done when

- `python -m pytest tests/http_api/test_chief_budget.py -q -p no:cacheprovider` passes and
  covers: an operator chief's `POST /runs` with `max_cost_usd` 11 is 403 with `ceiling: 10.0` and
  with 5 passes the gate; with `chief.max_runs_per_session` set to 2, two run starts pass and the
  third is 403; a run start the route answers with 400 (for example a missing field) leaves
  `runs_started` where it was, and a 2xx start counts; a decompose call does not count; a builder token and no token are unaffected; the
  migration runs twice; `GET /chief/session` reports the counts.
- `bandit -q -r src/pathly_orchestrator -ll` exits 0.

```check
$ python -m pytest tests/http_api/test_chief_budget.py -q -p no:cacheprovider
exit 0
prints passed
$ bandit -q -r src/pathly_orchestrator -ll
exit 0
```

## Reference

- ticket 08 (the `run` action list), ticket 05 (`chief_sessions`), ticket 07 (`GET /chief/session`)
- `src/pathly_orchestrator/http_server/blueprints/control/_helpers.py` (`max_cost_usd`)
- `src/pathly_orchestrator/db/queries/app_settings.py::get_setting`

## Answer

**Built**

- `http_server/chief_budget.py` (new, 197 lines): the cost ceiling and the run limit. `ceiling_usd(conn)` and `run_limit(conn)` read `chief.max_cost_usd_per_run` (default 10.0) and `chief.max_runs_per_session` (default 20) with `get_setting` on every call and fall back to the default for text that is not a usable number. `starts_a_run(rule, view_args)` decides which calls count: `POST /runs`, `/comms/goals/run`, `/comms/run`, `/comms/tasks/run` and the `retry` verb of `/runs/<run_id>/<action>`. `budget_refusal(conn, run_id, rule, method, view_args, bodies)` judges the cost of every reading of the body, then takes the slot, and returns `(error, extra_fields)` or None; it sets `flask.g.chief_run_slot`. `refund_run_slot(response)` is the `after_request` hook; `forget_run_slot()` clears a marker an earlier request left.
- `db/queries/chief_run_slots.py` (new, 42 lines, static SQL): `take_run_slot(conn, run_id, limit)` is `UPDATE chief_sessions SET runs_started = runs_started + 1 WHERE run_id = ? AND runs_started < ?` under `_get_write_lock` and returns `rowcount == 1`; `give_back_run_slot` is `... - 1 ... AND runs_started > 0`.
- `http_server/chief_gate.py` (210 lines): `chief_gate` calls `forget_run_slot()` first, and its last line is `_budget_refusal(...)` after the cite rule, so a call the gate itself refuses never reaches the count. `_refuse` takes extra fields (`ceiling`, `limit`) next to the usual `error`, `action`, `tier`, `allowed`. `http_server/app.py`: `app.after_request(refund_run_slot)` after `_log_response` (hooks run in reverse order, so the refund runs before the logger).
- `db/migrations_chief.py`: `add_chief_tables` adds `chief_sessions.runs_started INTEGER NOT NULL DEFAULT 0` with `ALTER TABLE` when the table exists without it (`_has_runs_started` checks `PRAGMA table_info` first; an `OperationalError` from another connection adding it in between is tolerated only when the column is there afterwards).
- `http_server/blueprints/control/_cost.py` (new, 48 lines) and `_helpers.py`: the ticket said `POST /runs` accepts any positive `max_cost_usd`; it never read the key. `_create_flow_run` now reads it with `flow_cost(body)` (default `DEFAULT_FLOW_COST_USD = 1.0`, which is `start_run`'s own default; a key that is present and is not a finite number above 0 is the route's 400 `Field 'max_cost_usd' must be a positive number`) and passes it to `start_run`. `as_cost` is shared with the gate, so the two cannot disagree about what a cost is.
- `http_server/chief_field_calls.py`: the `/runs` entry lists `max_cost_usd` as NUMBER. `tests/http_api/test_chief_gate_keys.py`: `WAITS_FOR_A_TICKET` is now empty (its only line was this key).
- `http_server/blueprints/chief/session.py`: `GET /chief/session` for an open session also returns `runs_started`, `max_runs_per_session` and `max_cost_usd_per_run`.
- Living docs: `src/pathly_orchestrator/CLAUDE.md` (the `GET /chief/session` line, a new "Cost and run limit" bullet in the Chief gate section, the stale "Not here yet" ticket-15 sentences replaced by a pointer, tree entries for `chief_budget.py`, `queries/chief_run_slots.py`, `control/_cost.py` and the `migrations_chief` note).
- Tests: `tests/http_api/test_chief_budget.py` (65 tests, the Done-when file), `tests/http_api/test_chief_budget_edges.py` (191: hostile costs, settings parser tables, the refund hook for many statuses and for a raising view, a stale marker, a late `before_request` hook, thread races, the tripwire for new `run` routes), `tests/db/test_chief_run_slots.py` (10), `tests/http_api/chief_budget_support.py` (helpers and the `STARTS` table of six start calls); `test_chief_routes.py` (the exact session dict has the three new fields) and `test_chief_gate_keys.py` edited; the three `INDEX.md` files regenerated.

**Proof** (Python 3.12.3 venv unless stated; `FLOW_DIR=pathly/features`)

- Test first: commit `c678fef` holds only test files. Run against the base source (a throwaway `git worktree` at `c678fef`, `PYTHONPATH=<worktree>/src`, `pathly_orchestrator.__file__` printed from the worktree; the worktree is removed): `python -m pytest tests/http_api/test_chief_budget.py -q -p no:cacheprovider` -> `53 failed, 3 passed`, exit 1; the five files together (budget, edges, `tests/db/test_chief_run_slots.py`, `test_chief_gate_keys.py`, `test_chief_routes.py`) -> `244 failed, 159 passed in 69.72s`. No collection error. The failures are the missing behaviour: a 403 where a start should pass, a 400 or 200 where the new answer was expected, `sqlite3.OperationalError: no such column: runs_started`, and `ModuleNotFoundError` for `chief_budget` and `chief_run_slots` raised inside the tests that import those new modules directly (not at collection). The 3 that pass in the Done-when file are controls of behaviour that already held (a chief cannot `PUT` settings, a session that is not open reports no counts, a start that takes no cost is not judged on one).
- Done when, `python -m pytest tests/http_api/test_chief_budget.py -q -p no:cacheprovider`, run fresh on the tree that is committed: `65 passed in 17.83s`, exit 0. The cases it covers: `max_cost_usd` 11 is 403 with `ceiling: 10.0` and 5 passes (`test_a_run_above_the_ceiling_is_refused_with_the_ceiling`, `..._within_the_ceiling_passes_and_the_route_takes_the_cost`, and at the ceiling passes while a hair above is refused); with `chief.max_runs_per_session` 2, two starts pass and the third is 403 (`test_with_a_limit_of_two_the_third_start_is_refused`); a start the route answers with 400 leaves `runs_started` where it was, a 2xx counts, and a later 400 does not take a counted one back; 409, an unknown goal or task and a retry with no cost give the slot back and a 500 keeps it; a decompose call, a stop, a read and the run verbs that start nothing do not count; a builder token and no token are unaffected; a call the gate refuses costs no slot and the chief hears the real reason when it is at the limit; the migration runs twice on an old and on a new database and on the live one; `GET /chief/session` reports the counts and the limits.
- `bandit -q -r src/pathly_orchestrator -ll`: exit 0, empty stdout (165 stderr warnings `nosec encountered ... no failed test` / `Test in comment` as before, none in a file I touched).
- `python -m pytest tests/http_api/test_chief_*.py -q -p no:cacheprovider` (every chief test, the audit, separator, tables and keys tests among them), on the final tree: `2071 passed in 694.82s (0:11:34)`, exit 0. An earlier run of the same command, before the last test additions, was `2052 passed in 691.89s`.
- Python 3.13.16 (`venv313`): `test_chief_budget.py`, `test_chief_budget_edges.py`, `tests/db/test_chief_run_slots.py` and the audit, separators, tables and keys tests (`test_chief_gate_audit.py`, `test_chief_gate_separators.py`, `test_chief_gate_tables.py`, `test_chief_gate_keys.py`) -> `492 passed in 349.42s`, exit 0; the final `test_chief_budget.py` and `tests/db/test_chief_run_slots.py` again after the last test edit -> `75 passed in 19.70s`.
- Neighbours: `python -m pytest tests/db tests/consistency tests/http_api/test_runs_control.py tests/dag_goals/test_cost_cap.py tests/telemetry/test_stage_provenance.py -q -p no:cacheprovider` -> `266 passed, 2 skipped in 54.47s`, exit 0 (the 2 skips are `tests/db/test_db.py:313` and `:341`, `PATHLY_DB_ONLY` legacy paths, not mine). I did not run the full repo suite (the ticket forbids it).
- Lint, each run on the final tree: `black --check src/ tests/` (661 files unchanged), `mypy src/ --ignore-missing-imports --no-strict-optional` (`Success: no issues found in 341 source files`), `python3 scripts/check_file_size.py` (`OK: 1036 source files checked; 18 known over 400 lines, none new, none grown.`), `python3 scripts/check_no_mirror_reads.py` (OK), `lint-imports` (1 kept, 0 broken), `python scripts/gen_test_index.py --check` (up to date). `git diff` adds no `noqa`, `nosec`, `type: ignore`, skip or xfail, no empty `except`, and touches no config or threshold.
- Mutation check (a scratch script in the session scratchpad; each mutation applied to a COPY of the repo with `PYTHONPATH=<copy>/src`, tests `test_chief_budget.py`, `test_chief_budget_edges.py`, `tests/db/test_chief_run_slots.py`, `test_chief_gate_keys.py`, `test_chief_routes.py`, one change at a time, the copy restored each time): 39 mutations. Killed: ceiling comparison doubled, `>=` instead of `>`, never refused; limit `<=` instead of `<`, the setting ignored; refund hook not registered, refund for 5xx, for 3xx, 499 not refunded, 400 not refunded, marker not consumed (refunds twice), refund allowed below zero, stale marker not cleared; `retry` not counted, `pause` counted, a decompose route counted, `/comms/tasks/run` not counted; cost check `not <= 0` (NaN passes), upper bound dropped (Infinity passes), a boolean taken as a cost, a string taken as a cost; limit parser: negative accepted, fraction truncated, no clamp, zero falls back; ceiling parser: garbage accepted; a flow start with no cost not judged, an unstated cost judged for every kind; the route ignores the cost, the route's 400 dropped; `GET /chief/session` omitting each of the three fields; the migration not adding the column, the `ALTER` error swallowed; the slot taken before the other checks (twice over). Three needed work. `ALTER` error swallowed survived: I added `test_a_failed_alter_that_leaves_the_column_missing_is_not_swallowed` and `test_a_column_another_connection_added_first_is_not_an_error` (a `sqlite3.Connection` subclass whose `ALTER TABLE` raises). The slot taken first and only once survived (the gate refunds its own 403, so a count cannot show the order; the first form of that mutation, which took the slot twice, was killed only because the count was 2): I added `test_a_session_at_its_limit_is_told_the_other_reason_first` (five refused calls at a limit of 0 must not answer "maxed") and `test_a_cost_above_the_ceiling_is_refused_as_such_at_the_limit`, after which both forms are killed. The refund-below-zero mutation was not applied at first (its SQL is split across source lines); with the pattern fixed it is killed by `test_the_count_never_goes_below_zero`. One mutation survives and is an equivalent mutant: `take_run_slot` as a read followed by a write, both inside `_get_write_lock`, which one process cannot interleave (the same read and write with a pause outside the lock IS killed by `test_threads_racing_for_the_last_slots_get_exactly_the_limit`); the single conditional `UPDATE` is kept because it also holds for a second server process on the same database file. The full run of all 39 was on the test files before the last five tests were added; the mutations those tests concern were re-run with them.
- Floor guard after the feature commit: `FLOW_DIR=pathly/features FLOW_TICKETS=tasks python3 scripts/floor-guard.py chief-agent 15 1709e7524808408912cd5bbb95082b2bd7bcbba3` printed `floor guard: clean`, exit 0, run on the staged tree (the test-first commit plus the staged feature changes) just before the feature commit.

**Decisions**

- Retry, pause, resume, advance, reroute: `retry` counts one and `pause`, `resume`, `advance` and `reroute` do not. `retry` calls `start_run` and so starts a new run (a retry of a finished run can spend again); the other four act on a run that already exists. The deciding table is `chief_budget.STARTS_A_RUN` / `STARTING_VERBS`, and `test_every_route_of_the_run_action_is_counted_or_decided_by_its_verb` pins both against `chief_routes`, so a new `run` route or verb must be decided. A retry that answers `ok: false` with 200 (the run is still active, or the registry does not know it) keeps its slot: only a 4xx gives one back, as the ticket says.
- `POST /runs` did not read `max_cost_usd`: the ticket's premise was stale. The route now reads and validates it (400 on a bad value, passed to `start_run`), so the ceiling means something; Studio's `apiCreateRun` never sends the key, so non-chief callers of `POST /runs` that send none run exactly as before (the route used to ignore the key, and still uses `start_run`'s `$1` when it is absent).
- A flow start that states no `max_cost_usd` is judged at `DEFAULT_FLOW_COST_USD` (1.0), the cost the route will really run it at: fail closed, so a ceiling set below $1 still holds. Only `kind: flow` gets that default; a single, evaluator or goal start has no per-run cost, so one that states none is not judged. A `max_cost_usd` key that is present is judged whatever the kind, even though those kinds ignore it, so a chief cannot slip an over-ceiling cost past the gate by changing `kind`.
- The gate and the route share `_cost.as_cost`: a cost is a finite number above 0, not a boolean, string, list or `null`. `NaN` and `Infinity` are accepted by Python's JSON parser and make a cost comparison always false, so they would mean no cap; the chief gets 403 `max_cost_usd must be a finite number above 0` with `ceiling`.
- A setting that is not usable falls back to its default (ceiling: text that does not parse, `NaN`, `Infinity`, 0 or less; limit: negative, fractional, not finite). The default is a bound too, so a corrupt setting never means unlimited. A limit of 0 means no run may start, and a limit above 2^62 is read as 2^62 (SQLite binds 64 bits).
- `PUT /db/settings/<key>` has no allow-list of names (it stores `str(value)` for any key), so the two settings needed no registration and a chief token cannot set them because the gate refuses that route for it (`test_a_chief_cannot_change_its_own_limit`).
- Every reading of the body (`_bodies`) is judged for the cost; the slot is taken once per request.
- The counter is in the session row, so a new chief session starts at 0, and the person "raises the limit" with the setting, which is read on every call (`test_the_user_raises_the_limit_for_the_session_already_open`).

**Shortcuts taken**

- A goal run, a board run and a task run state no per-run cost, so for them only the count bounds a chief; a goal run's own cap is the separate `goal.max_cost_usd` setting.
- `handle_retry` and the `/runner/*` routes still accept `NaN` from a caller with no chief token, as before; only the chief gate refuses it. Changing them is outside this ticket.
- The refund is a response hook: if the process dies between the slot and the response, the slot stays used (fails closed). If the refund `UPDATE` itself fails it is logged at warning and the response is returned as it was.
- The count is taken when the gate allows the call, not when the run actually starts, so a start that the route accepts with 200 but that does nothing (`ok: false`) still uses a slot.

**For later tickets**

- Ticket 16 (the chief retires a binding): `/comms/supersede` and the other routes are untouched; nothing here counts them.
- Round two billing: `chief_sessions.runs_started` and `chief_budget.ceiling_usd` are the hooks to extend with a cost summed across the session's runs; `GET /chief/session` already reports the ceiling.
- A new route that starts work must go into `chief_budget.STARTS_A_RUN` (or a run verb into `STARTING_VERBS`) and into `STARTS` in `tests/http_api/chief_budget_support.py`; the tripwire in `test_chief_budget_edges.py` fails until it does.
- `/runs` now lists `max_cost_usd` in `chief_field_calls.py`; a later key goes in the same `keys` dict.

**Minors noticed, not fixed**

- `handle_retry` accepts `NaN` and `Infinity` for `max_cost_usd`, and the `/runner/start` and `/runner/retry` routes do the same (the runner then never stops on cost); only the chief gate refuses them.
- `POST /runs` with `kind: single|evaluator|goal` ignores `max_cost_usd` silently (no 400 for a bad value there).
- `bandit` prints `nosec encountered ... no failed test` and `Test in comment: ... is not a test name or id` warnings on stderr (it exits 0), and `mypy` prints `annotation-unchecked` notes; both existed before.
- `CLAUDE.md` says 19 files are over the size limit; `check_file_size.py` reports 18 known (not touched here).
