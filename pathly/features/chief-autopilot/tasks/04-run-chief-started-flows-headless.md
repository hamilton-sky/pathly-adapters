# Run a chief-started flow headless, and list packaged flows as `flow`

Type: task
Status: resolved
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

**Built** (work started at f1c89b75; failing test a9604ce5, then the change):
- `http_server/blueprints/control/_helpers.py::_create_flow_run`: reads `interactive` (default
  `True`); anything but a JSON boolean is 400 `Field 'interactive' must be a boolean`; a caller
  whose token is a live chief (`run_identity.is_chief_run(caller_identity(request))`, lazy
  imports) gets `False`. `start_run` is now always called with `interactive=` (`True` when no
  field and no chief, which is `start_run`'s own default, so Studio's New-run button is unchanged).
- `http_server/chief_field_calls.py`: `/runs` POST has `not_for_chief=("interactive",)`; module
  docstring lists it.
- `db/queries/run_history_read.py`: `FLOW_NAMES` is built at import by `_packaged_flow_names()`
  from the `flow:` key of every packaged `core/flows/*.flow.yaml` (found with
  `catalog_items._find_data_root`, a db sibling), minus `goal-loop`. Today: consultation, debug,
  explore, feature-consultation, project-consultation, quick-fix, team, team-build, test.
- `tests/http_api/test_runs_flow_headless.py` (new, 13 tests), `tests/INDEX.md`,
  `tests/http_api/INDEX.md`, `src/pathly_orchestrator/CLAUDE.md` (not_for_chief list, the RunSpec
  line of the control blueprint, `FLOW_NAMES`).

**Proof**:
- `python -m pytest tests/http_api/test_runs_flow_headless.py -q -p no:cacheprovider`: 13 passed,
  exit 0 (chief token -> `interactive=False`; tokenless no field -> `True`; tokenless `false` ->
  `False`; `"false"`, 0, 1, null, [], {} -> 400 and no start; a chief sending `true` or `false`
  -> the gate's 403 naming `interactive`; all 10 packaged flows seeded as bare-uuid rows list as
  `flow`, `goal-loop` as `loop`). At a9604ce5 it was 9 failed, 4 passed (the gate case and the
  default case already held).
- `python -m pytest tests/http_api -q -p no:cacheprovider`: 2564 passed, exit 0.
- Extra: `python -m pytest tests/db tests/dag_goals -q -p no:cacheprovider`: 401 passed, 2
  skipped, exit 0 (they import `FLOW_NAMES` and `_classify_kind`).
- Lint chain from commands.md: exit 0 (mypy clean, file sizes none grown, lint-imports kept).

**Decisions**:
- An explicit `null` for `interactive` is 400 (only a missing key takes the default), so a body
  that names the key must give a boolean.
- A chief token wins over the body; the gate already refuses a chief's `interactive` key, so the
  two never meet in practice.
- `FLOW_NAMES` keeps its name and type (a set) so the db and dag_goals tests that import it hold;
  the `flow:` key is read with a line regex rather than YAML, so the read-model needs no YAML parse.

**Shortcuts taken**: `FLOW_NAMES` is read once at import, so a flow file added while the server
runs is not seen until restart (packaged flows change only with a release). A project-local or
DB-only flow definition is not included; worth it if user-defined flows start running through
`start_run`.

**For later tickets**: `POST /runs` with a chief token now always passes `interactive=False`; a
test that stubs `start_run` sees an `interactive` keyword on every flow start.
