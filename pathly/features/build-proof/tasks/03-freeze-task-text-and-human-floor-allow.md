# Freeze a task's text at claim and let only a human set its floor allow list

Type: task
Status: resolved
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

Work started at commit `266eac6f5d9cdc4904936ccf7f9e1260a6e2f3c5`. Test-only commit: `9fd776d`
(`test(build-proof): 03 failing test`). At that commit `test_task_claim_snapshot.py` fails at
collection with `ModuleNotFoundError: No module named 'pathly_orchestrator.db.queries.task_proof'`
(exit 2), and `test_floor_allow_route.py` gives `12 failed, 1 passed`: the route answers 404
(`assert 404 == 200`, `404 == 403`, `404 == 400`) and `_row` hits `no such column: claimed_text`.
The one pass is the 404-for-a-missing-task case, which an absent route also satisfies.

**Built**

- `src/pathly_orchestrator/db/migrations_incremental.py`: two entries in the
  `_add_additive_migrations` list, `("comms_messages", "claimed_text", "TEXT")` and
  `("comms_messages", "floor_allow", "TEXT")`, with a three-line comment like its neighbours.
- `src/pathly_orchestrator/db/queries/comms_tasks.py`: the existing `attempts=` line of
  `claim_task`'s one `UPDATE` now also sets `claimed_text=COALESCE(claimed_text, text)`. Still
  418 lines.
- `src/pathly_orchestrator/db/queries/task_proof.py` (new, 143 lines): `get_task`,
  `tasks_claimed_since`, `tasks_completed_since`, `set_floor_allow`, plus private `_instant` and
  `_since`. Every SQL statement is one fixed literal.
- `src/pathly_orchestrator/http_server/blueprints/comms/tasks_floor.py` (new, 88 lines):
  `POST /comms/tasks/floor-allow`. Registered in `blueprints/comms/__init__.py` (import and
  `all_blueprints`). The run-identity, `proof.floor`, `db` imports are lazy inside the route.
- Living docs: `src/pathly_orchestrator/CLAUDE.md` (the route in the comms endpoint list, a
  "Frozen task text and the human-only floor allow list" paragraph after the human escalation
  gate, which names the tokenless-caller limit, and a `task_proof.py` line in the `db/queries`
  listing); root `CLAUDE.md` blueprint map `comms/` line now names `tasks_floor`.
- Tests (in the test-only commit): `tests/db/test_task_claim_snapshot.py` (14 tests),
  `tests/http_api/test_floor_allow_route.py` (13 cases), regenerated `tests/INDEX.md`,
  `tests/db/INDEX.md`, `tests/http_api/INDEX.md`.

**Proof** (each run fresh after the last code edit)

- `python -m pytest tests/db/test_task_claim_snapshot.py -q -p no:cacheprovider`: `14 passed in
  5.15s`, exit 0. Covers: a fresh `get_db()` has both columns; an old DB (a fresh one with both
  columns dropped and a claimed task inserted, then `_run_migrations` twice) gets both back and
  the old row reads `NULL` in both; the first `claim_task` copies the text (`claimed_text ==
  FIRST`, `attempts == 1`); after `update_message_text(SECOND)`, `task_retry.retry_task` and a
  second claim, `text == SECOND`, `claimed_text == FIRST`, `attempts == 2`; a `run_id="build"`
  claim freezes too; `set_floor_allow(["skip","config","skip"])` stores `["config","skip"]` and
  keeps `claimed_text`; `set_floor_allow(["skip"], refreeze=True)` copies `SECOND` into
  `claimed_text`; `[]` clears; a missing id or non-task row returns `False` and stores nothing;
  `get_task` reads a task and a decision, `None` for missing or soft-deleted;
  `tasks_claimed_since(..., "g1", since)` gives only the g1 task claimed in the window, while
  `goal_id=None` gives the three in `(feature, feat)` (not the other scope, the unclaimed one or
  the one claimed in 2020); the window compares times, not strings (`...10:00:00.25Z` includes
  a claim stamped `...10:00:00.250000+00:00`, which a string compare would drop);
  `tasks_completed_since` keeps only `done` tasks in the window, goal-scoped likewise.
- `python -m pytest tests/http_api/test_floor_allow_route.py -q -p no:cacheprovider`: `13 passed
  in 4.29s`, exit 0. Covers: no token gives 200 `{"ok": true, "allow": ["skip"]}` and the row
  stores `["skip"]`; a token from `run_tokens.mint_run_token` gives 403 and `floor_allow` stays
  `NULL`; a revoked token is treated like none (200, the documented limit); `["nope"]` gives 400
  whose error names `nope` and `skip`, `suppress`, `plan-edit`, `task-edit`, nothing stored; a
  missing id gives 404; a `decision` row gives 400 naming `task`; malformed bodies (no
  `message_id`, empty `message_id`, no `allow`, `allow` as a string, `refreeze: "false"`) give
  400 and store nothing; `refreeze: true` copies the live text into `claimed_text`, `false`
  keeps it.
- `python scripts/check_file_size.py`: `OK: 943 source files checked; 19 known over 400 lines,
  none new, none grown.`, exit 0. `wc -l` of `comms_tasks.py`: 418.
- The ```check block: the same three commands, each exit 0, printing `passed`, `passed` and
  `none grown` (above).
- Lint (the full chain from `commands.md`): exit 0. black `499 files would be left unchanged`;
  mypy `Success: no issues found in 283 source files`; file size `none new, none grown`; mirror
  reads OK; `All test INDEX.md files up to date.`; lint-imports `Contracts: 1 kept, 0 broken.`;
  bandit no findings (only the pre-existing `nosec` notices); adapters OK; entry points OK.
- Smoke: exit 0. Build (`python -m build --wheel`): `Successfully built
  pathly_adapters-2.24.1-py3-none-any.whl`, exit 0; the wheel lists
  `pathly_orchestrator/db/queries/task_proof.py` and `.../blueprints/comms/tasks_floor.py`.
- Test (`python -m pytest tests/ -q -x -p no:cacheprovider`): `2472 passed, 14 skipped in
  465.69s`, exit 0. It includes `test_comms_body_encoding.py`, whose live `url_map` sweep now
  covers the new route (it reads its body through `read_json_body`).

**Decisions**

- `get_task` returns the live row of any `type` (`None` when missing or soft-deleted), so the
  route can tell 404 (no row) from 400 (not a task) with one read. Callers that need a task
  check `row["type"]`.
- The `*_since` queries select the scoped rows with a fixed literal and filter the window in
  Python with `datetime.fromisoformat` (a naive stamp counts as UTC). `claim_task` stamps
  `isoformat()` (`+00:00`, and no fraction when microseconds are 0) while event `ts` values
  end in `Z`, and a string compare misorders the same instant. Results are sorted oldest first.
  A `since` that does not parse raises `ValueError` (a caller bug, not a fail-open case).
- Scoping mirrors `_count_incomplete`: `if goal_id:` goal-only (board and scope ignored, as
  `count_incomplete_tasks_for_goal` does), elif `scope:` `(board, scope)` with `board` as
  passed, else `[]`. Soft-deleted rows are excluded.
- `set_floor_allow` stores `json.dumps(sorted(set(allow)))` (so a `parse_allow` frozenset
  works), updates only a live `type='task'` row and returns whether one was updated. Validation
  stays in the route (`proof.floor.parse_allow`), so the db layer imports nothing new. `[]` is
  stored as `[]` (an explicit empty list), not `NULL`.
- The route: the 403 runs before the body is read, exactly as `blueprints/core/fsm.py` tests
  `caller_identity(request).kind == "run"`. `allow` must be a JSON list (400 naming the valid
  categories otherwise); `parse_allow`'s `ValueError` text is the 400 body for an unknown name;
  `refreeze` must be a JSON boolean (default `false`), so `"false"` cannot refreeze by being a
  truthy string. 200 returns the stored, sorted list.

**Shortcuts taken**

- The route writes no board audit line or `COMMS_UPDATE` broadcast. The stored `floor_allow`
  value is the record, and Studio has no control that would refresh on it yet. Worth adding
  when the Studio control lands (map.md § Open questions), so a human sees who allowed what.
- `*_since` reads every scoped task with a stamp and filters in Python. A goal or feature has a
  bounded DAG, so this is cheap; it would need an index-friendly SQL window only if one scope
  ever held thousands of tasks.

**For later tickets**

- Import as `from pathly_orchestrator.db.queries.task_proof import get_task,
  tasks_claimed_since, tasks_completed_since, set_floor_allow`. Rows are plain dicts
  (`SELECT *`), so `claimed_text`, `floor_allow`, `claimed_at`, `completed_at`, `attempts` and
  `text` are all there.
- `floor_allow` is raw JSON text (or `NULL`): read it with `proof.floor.parse_allow(
  json.loads(row["floor_allow"] or "[]"))`. `claimed_text` is `NULL` for a task claimed before
  this feature; per spec, proof then falls back to `text` and skips `task-edit` for that task.
- Tickets 05/07 can pass `proof_base["started_at"]` straight in as `since` (either `Z` or
  `+00:00` form, or a `datetime`); an unparseable value raises `ValueError`, so a gate that
  must fail open should catch it.
- `/comms/tasks/claim`, `/comms/tasks/run` and the scheduler all freeze the text through
  `claim_task`; `_release_claim` (tasks.py) and `retry_task` keep `claimed_text`, so a later
  claim never refreshes it. Only `set_floor_allow(..., refreeze=True)` does.
