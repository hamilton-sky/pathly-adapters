# Cap what one chief session can spend and start

Type: task
Status: open
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
the gate allows the call, not when the run succeeds; a failed start still uses a slot (fail
closed). Put the check in its own module (for example `http_server/chief_budget.py`), called from
`chief_gate` after the action and project checks.

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
  third is 403; a decompose call does not count; a builder token and no token are unaffected; the
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
