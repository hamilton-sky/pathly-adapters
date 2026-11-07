# Show consult runs and routed questions in the run views and the chief's notices

Type: task
Status: open
Blocked by: 01, 02, 16
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/db/queries/run_history_read.py, src/pathly_orchestrator/db/queries/run_consults.py (new), src/pathly_orchestrator/db/queries/chief_session_runs.py, src/pathly_orchestrator/http_server/blueprints/chief/notices.py, src/pathly_orchestrator/supervisor/chief_presets.py, tests/http_api/test_chief_notices_consults.py (new), src/pathly_orchestrator/CLAUDE.md, src/pathly_orchestrator/http_server/chief_field_reads.py, tests/INDEX.md, tests/http_api/INDEX.md

The chief (and the person, through Studio's run pages) must see which questions a role answered
and which wait for the person.

1. **Kind `consult`.** `run_history_read._classify_kind` returns `consult` for a run id that
   starts `consult-` (before the stage pattern). `list_runs` lists consult runs as top-level rows.
   A parent's window cost in `_run_cost` (flow, decompose, loop parent) leaves out invocations
   whose `category` is `consult` (ticket 16 stamps it), so a consult that ran on the same board is not counted in the
   parent and again on its own row. `run_history_read.py` is at 389 lines: put the new helpers in
   new `src/pathly_orchestrator/db/queries/run_consults.py` (new) and move `_run_outcome` there
   too if the file would pass 400 (re-export it, `chief_session_runs` imports it).
2. **A run's consults.** `run_consults.consults_of_run(conn, run_row) -> list[dict]`:
   `[{question_id, role, status, consult_run_id, reason}]` from `consult_routes` (ticket 01) whose
   `asking_run_id` is the run or one of its children (`run_history_read._child_rows`: a loop
   parent's `sched-` tasks, a flow's stages). `get_run_detail` adds `run.consults` and
   `run.waiting_for_person` (those consults whose status is `to_person` or `withheld` and whose
   question has no answer yet).
3. **Notices.** `blueprints/chief/notices._notice` adds `consults` and `waiting_for_person` from
   the same helper (`chief_session_runs.run_notice` reads the row it needs). `GET /chief/notices`
   takes `limit` (default 50, an integer 1 to 200, else 400 `{"error": "limit must be an integer
   from 1 to 200"}`), applied in `chief_session_runs.ended_unread_runs`.
   `chief_session_runs.record_session_run` also deletes the project's rows marked read more than
   30 days ago (one `DELETE`), so the table no longer grows forever (round one's HANDOFF 08).
4. **Operator text.** `OPERATOR` in `src/pathly_orchestrator/supervisor/chief_presets.py` says, in one bullet, that agents'
   questions to a role are answered by consult runs Pathly starts, that a notice's `consults` give
   each one's status, and that only questions to the user (`to: human`, including those a role
   handed on) wait for the user's answer. It stays under its 4000-character limit
   (`tests/http_api/test_chief_cli.py`; 3797 today): shorten another line if it must.

## Not in this ticket

- Studio's Monitor category for consult runs: ticket 10. Studio's Chief notices list shows the
  new fields only if a later ticket adds them (the API carries them now).
- Notices typed into the chief's tab: round four.

## Done when

- `python -m pytest tests/http_api/test_chief_notices_consults.py -q -p no:cacheprovider` passes
  and covers: `GET /runs` lists a `consult-` run as `kind: consult` and a loop parent's cost does
  not include it; `GET /runs/<id>` of a single run with one answered and one handed-on route shows
  both in `consults` and `waiting_for_person: 1`, and a loop parent shows its `sched-` tasks'
  consults; a notice carries the same; `limit=2` returns two of three notices, `limit=0` and
  `limit=x` are 400; a row read 31 days ago is gone after the next `record_session_run` and one
  read yesterday stays.
- `python -m pytest tests/http_api/test_chief_cli.py -q -p no:cacheprovider` passes (Operator text
  under 4000 characters).
- All existing tests under `tests/http_api -k "chief or runs"` and `tests/db` still pass.

```check
$ python -m pytest tests/http_api/test_chief_notices_consults.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/http_api/test_chief_cli.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/http_api tests/db -q -p no:cacheprovider -k "chief or runs or run_history"
exit 0
```

## Reference

- spec.md § Stories ("The chief can tell me what happened"), § Interfaces
- round one `pathly/features/chief-autopilot/tasks/08-tell-the-person-when-a-chief-run-ends.md` (Answer)
- round one learnings (07, 08)

## Answer
