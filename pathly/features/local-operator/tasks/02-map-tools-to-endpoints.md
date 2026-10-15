# Map the 6 operator tools to server endpoints

Type: task
Status: resolved
Blocked by: 01
Test first: yes

For each of ticket 01's settled tools, find the existing server
endpoint that implements it (route, method, required args, auth):

- `spawn_planner` → the run-start path with the planner adapter/role
  (find how the supervisor routes a planner stage; reuse it, don't
  invent a new spawn path).
- `start_run` → existing run start (`POST /runs` or the goal-run
  route — name the real one).
- `pause_run` / `resume_run` / `retry_stage` → the existing run
  control routes.
- `post_message` → the comms post route (as the human's nudge —
  stamped accordingly, never as the chief).

Where an endpoint is missing or its shape doesn't fit a tool, add the
thinnest possible wrapper route (no new business logic — assemble from
existing queries/commands). Record every mapping in the Answer as a
table: tool → method + path → wrapper? (yes/no).

Also verify: a spawn refused by cost ceilings / daycap surfaces the
same error shape the operator will relay (spec.md § Edge cases).

## Not in this ticket

- The Electron tool loop: ticket 03. New run-start semantics: none —
  reuse only.

## Done when

- `python -m pytest tests/local_operator/test_tool_mapping.py -q -p no:cacheprovider` passes and covers: each of the 6 tools resolves to a route that exists and accepts the settled args (call the route with a fixture; wrappers tested where added); a ceiling-hit spawn returns the documented refusal shape.
- `python scripts/check_file_size.py` exits 0.

```check
$ python -m pytest tests/local_operator/test_tool_mapping.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- spec.md § Interfaces; ticket 01's Answer (tool/arg names)
- `src/pathly_orchestrator/http_server/blueprints/` (route registry)

## Answer

Resolved 2026-10-14. No new run-start semantics and no thin wrappers were
needed: every server-run action executes by dispatching IN-PROCESS to the
route a human click uses (`blueprints/hq/_action_exec.py`, Flask test client
on loopback — the middleware's trust for local callers), so validation,
refusal shapes, board posts and SSE broadcasts are the endpoint's own.

| Action | Method + path | Wrapper? |
|---|---|---|
| `pause_run` | `POST /runs/<run_id>/pause` | no |
| `resume_run` | `POST /runs/<run_id>/resume` | no |
| `retry_run` | `POST /runs/<run_id>/retry` (`flow` from the run, 50 iterations / $10 — RunControls' defaults) | no |
| `stop_run` | `POST /runs/<run_id>/stop` | no |
| `run_goal` | `POST /comms/goals/run {goal_id, project_root}` | no |
| `plan_goal` | `POST /comms/goals/decompose {goal_id, mode: planner}` | no |
| `post_note` | `POST /comms/post {from: human, type: note}` (what Studio's note post sends) | no |
| `diagram_artifact` | Studio: the editor's diagram one-shot | n/a (server validates + audits) |
| `add_diagram_to_board` | Studio: `addDiagramToBoard` | n/a (server validates + audits) |

New server surface (`blueprints/hq/`): `actions.py` — `GET /hq/actions`
(catalog + availability + presets) and `PUT /hq/actions/available`;
`actions_run.py` — `POST /hq/actions/check` (proposals → cards; not enabled /
not available → dropped; bad args or a target in the wrong state → an
`invalid` record), `POST /hq/actions/run` (resolve again, fingerprint compare
→ `stale`, else execute + audit; Studio-run → `approved` + resolved target),
`POST /hq/actions/report` (Studio-run result → audit). Target resolution and
fingerprints: `_action_targets.py` (runs by id or unique prefix; goals and
artifacts by the packet's short id or title, ambiguity rejected). Catalog:
`hq_actions.py`; availability: `hq_settings.get/set_hq_available_actions`.

Refusal shape: a spawn refused by the route (busy board, ceilings) comes back
as the route's own `reason` and the card ends `failed: board busy` — one
attempt, no retry loop (`test_a_spawn_refusal_reaches_the_card`).

`tests/local_operator/test_tool_mapping.py` (20 tests) green;
`tests/local_operator` 37 passed. `check_file_size.py`: OK, none new, none
grown. Black, mypy, lint-imports green; bandit is not installed in `.venv`,
not run.
