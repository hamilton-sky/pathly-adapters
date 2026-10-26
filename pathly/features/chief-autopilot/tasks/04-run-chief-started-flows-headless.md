# Run a flow started through `POST /runs` headless, and list it as a flow

Type: task
Status: open
Blocked by: —
Test first: yes

Spike S11 and S12. `POST /runs {"kind": "flow"}` (`blueprints/control/_helpers.py::_create_flow_run`)
calls `supervisor.api.start_run` without `interactive`, whose default is `True`, so each stage
opens an interactive claude tab that stops at the "Bypass Permissions mode" dialog. The goal
executor already passes `interactive=False` (`goal_executor.py`, "Goal executors are headless
one-shots per stage"). Pass `interactive=False` from `_create_flow_run`; Studio's Start button
uses `/runner/start` and keeps choosing for itself.

`GET /runs` listed that explore run as `kind: single`. `db/queries/run_history_read.py::_classify_kind`
calls a run `flow` when its `adapter` column is one of `FLOW_NAMES`; find what a `/runs` flow
start records there and make the two agree, so every packaged flow (`core/flows/*.flow.yaml`)
started through `POST /runs` lists as `flow`.

## Not in this ticket

- The `team` executor of a goal run: already headless.
- Choosing interactive from the chief: the chief never gets a tab of its own for a run.

## Done when

- `python -m pytest tests/http_api/test_runs_flow_headless.py -q -p no:cacheprovider` passes and
  covers: a `POST /runs` flow start reaches `start_run` with `interactive=False` (patched
  `start_run` records it); the first spawn the fake host receives is headless (`-p` argv, not the
  interactive one); every flow name in `core/flows/` started this way lists in `GET /runs` with
  `kind: "flow"`.
- All existing `tests/http_api` tests still pass.

```check
$ python -m pytest tests/http_api/test_runs_flow_headless.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/http_api -q -p no:cacheprovider
exit 0
```

## Reference

- spike19-part-b-report.md § Surprises ("An explore flow run ... opened an interactive claude")
- `src/pathly_orchestrator/supervisor/api.py::start_run`, `src/pathly_orchestrator/db/queries/run_history_read.py`

## Answer
