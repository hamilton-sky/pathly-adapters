# Freeze a task's text at claim and let only a human set its floor allow list

Type: task
Status: open
Blocked by: 02
Test first: yes

Two additive columns, in the `(table, column, type)` list in
`db/migrations_incremental.py::_add_additive_migrations`: `("comms_messages", "claimed_text",
"TEXT")` and `("comms_messages", "floor_allow", "TEXT")` (a JSON list of category names).

`db/queries/comms_tasks.py::claim_task` also sets `claimed_text=COALESCE(claimed_text, text)` in
its one `UPDATE`. That freezes the text, and with it any ```check block, on the first claim, and
keeps it across retries. Every claim goes through `claim_task`: the scheduler's
`sched-<id>#<n>` claims and `POST /comms/tasks/claim` (team-flow builders claim with
`run_id: "build"`). `comms_tasks.py` is frozen at 418 lines, so edit the existing `attempts=`
line in place. The file must not grow.

New `db/queries/task_proof.py`. Bandit applies: fixed query text, no string building. The two
`*_since` queries are goal-scoped when `goal_id` is given, else scoped to `(board, scope)`,
mirroring `fsm/gates/tasks.py::_count_incomplete`.

- `get_task(conn, id)`;
- `tasks_claimed_since(conn, board, scope, goal_id, since)`: tasks with `claimed_at >= since`;
- `tasks_completed_since(conn, board, scope, goal_id, since)`: `task_status='done'` and
  `completed_at >= since`;
- `set_floor_allow(conn, id, allow, refreeze=False)`: stores the JSON list. With `refreeze`, it
  also copies the live `text` into `claimed_text`, which is how a human corrects a task's
  checks.

New blueprint `http_server/blueprints/comms/tasks_floor.py` with
`POST /comms/tasks/floor-allow` `{"message_id", "allow": [...], "refreeze": false}`, registered
in `blueprints/comms/__init__.py`. The route:

- refuses with 403 any caller whose `run_identity.caller_identity(request).kind == "run"`, the
  same rule `blueprints/core/fsm.py` applies to `force_past_gate`;
- validates `allow` with `proof.floor.parse_allow` (400 naming the valid categories);
- returns 404 for a missing row and 400 for a row that is not `type='task'`;
- returns 200 `{"ok": true, "allow": [...]}`.

Imports stay lazy inside the route.

Living docs: the route and the two columns in `src/pathly_orchestrator/CLAUDE.md` (comms tasks
section). Add `tasks_floor` to the `comms/` line of the blueprint domain map in the root
`CLAUDE.md`. Name the limit: a caller with no token is treated as a human, as for
`force_past_gate`.

## Not in this ticket

- Reading `claimed_text` and `floor_allow` during proof: tickets 05, 06 and 07.
- A Studio control for the allow list: out of scope (Studio UI). map.md § Open questions.
- Re-opening a failed task after a human fixes it: existing Studio and executor controls,
  unchanged.

## Done when

- `python -m pytest tests/db/test_task_claim_snapshot.py -q -p no:cacheprovider` passes. It
  covers: a fresh DB and an old DB without the columns both end up with `claimed_text` and
  `floor_allow`; the first `claim_task` copies the text; after `text` changes and the task is
  retried (`task_retry.retry_task`) and claimed again, `claimed_text` is still the first text;
  `set_floor_allow(..., refreeze=True)` copies the new text; `tasks_claimed_since` respects
  `goal_id`.
- `python -m pytest tests/http_api/test_floor_allow_route.py -q -p no:cacheprovider` passes. It
  covers: no token gives 200 and stores `["skip"]`; a live run token (`run_tokens.mint_run_token`)
  gives 403 and stores nothing; `["nope"]` gives 400; a missing id gives 404; a non-task message
  gives 400.
- `python scripts/check_file_size.py` exits 0 (`comms_tasks.py` did not grow).

```check
# The conductor runs this block before review.
$ python -m pytest tests/db/test_task_claim_snapshot.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/http_api/test_floor_allow_route.py -q -p no:cacheprovider
exit 0
prints passed
$ python scripts/check_file_size.py
exit 0
prints none grown
```

## Reference

- spec.md § Decisions ("Where the snapshot lives", "Who may set a floor allow list"),
  § Interfaces, § Migration and compatibility
- `src/pathly_orchestrator/db/queries/comms_tasks.py::claim_task`
- `src/pathly_orchestrator/http_server/blueprints/core/fsm.py` (the `force_past_gate` 403)
- `src/pathly_orchestrator/http_server/run_identity.py::caller_identity`
- `tests/fsm_flows/test_human_escalation_gate.py` (minting a run token in a test)

## Answer
