# Run a chief-started flow headless, and list packaged flows as `flow`

Type: task
Status: open
Blocked by: 10
Test first: yes
Level: 2
Touches: src/pathly_orchestrator/http_server/blueprints/control/_helpers.py, src/pathly_orchestrator/http_server/chief_field_calls.py, src/pathly_orchestrator/db/queries/run_history_read.py, tests/http_api/test_runs_flow_headless.py, src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/http_api/INDEX.md

Spike S11 and S12. `POST /runs {"kind": "flow"}`
(`src/pathly_orchestrator/http_server/blueprints/control/_helpers.py::_create_flow_run`) calls
`supervisor.api.start_run` without `interactive`, whose default is `True`, so each stage opens an
interactive claude tab that stops at the "Bypass Permissions mode" dialog. Studio's Monitor
New-run button (`studio/src/renderer/src/components/Monitor/RunList/NewRunButton/hooks/useNewRunForm.ts`
→ `store/commsApi/boardRun.ts::apiCreateRun`) posts the same route with no `interactive`, and its
behaviour is the person's, so it stays as it is.

In `_create_flow_run`, pass `interactive=False` when the caller holds a chief token
(`run_identity.caller_identity(request)` role `chief`; ticket 10 makes that identity reliable) or
when the body says `"interactive": false`; otherwise keep today's default. Accept `interactive` as
a boolean (400 for anything else). A chief cannot ask for an interactive run: list `interactive` under
`not_for_chief` for `/runs` in `src/pathly_orchestrator/http_server/chief_field_calls.py`, that
module's convention for keys a chief must not send.

`GET /runs` listed the spike's explore run as `kind: single`:
`src/pathly_orchestrator/db/queries/run_history_read.py::_classify_kind` calls a run `flow` only
when its `adapter` is in `FLOW_NAMES`, a hard-coded set of five. Derive it from the packaged flow
files (`src/pathly_data/core/flows/*.flow.yaml`, the `flow:` key), excluding `goal-loop`, which
stays `loop` on purpose.

## Not in this ticket

- The `team` executor of a goal run: already headless (`goal_executor`).
- Studio's New-run form: unchanged.

## Done when

- `python -m pytest tests/http_api/test_runs_flow_headless.py -q -p no:cacheprovider` passes and
  covers: a chief-token flow start reaches `start_run` with `interactive=False`; a tokenless start
  with no field keeps the default, and with `"interactive": false` is headless; a non-boolean is
  400; a chief sending `interactive` is refused by the gate; every packaged flow but `goal-loop`
  lists in `GET /runs` as `kind: "flow"`, and `goal-loop` as `loop`.
- All existing `tests/http_api` tests still pass.

```check
$ python -m pytest tests/http_api/test_runs_flow_headless.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/http_api -q -p no:cacheprovider
exit 0
```

## Reference

- spec.md § Decisions ("Headless flows"), review M7
- `src/pathly_orchestrator/supervisor/api.py::start_run`, `src/pathly_orchestrator/supervisor/registry.py::_record_run_history`

## Answer
