# Show consult runs and routed questions in the run views and the chief's notices

Type: task
Status: resolved
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

Work started at `142c668d851f3821a40f00125253b63d47d966f7`; attempt 2 built on HEAD `5fd6168`
(attempt 1's test commit cherry-picked on `4d5a108`, which adds `chief_field_reads.py` to
Touches). Test-only commit `5fd6168`: there all 8 tests of
`tests/http_api/test_chief_notices_consults.py` fail (kind `single` for a `consult-` run,
`KeyError: 'consults'`, the chief gate's 403 on `limit`, the 31-day row kept). Attempt 1 stopped
because the gate's key table is outside its first Touches (kept on `backup-09-attempt1`).

**Built**

- `src/pathly_orchestrator/db/queries/run_consults.py` (new): `is_consult_run`,
  `consults_of_run(conn, run_row)` (routes whose `asking_run_id` is the run or one of
  `run_history_read._child_rows`, imported lazily), `waiting_for_person(conn, consults)`
  (`to_person`/`withheld` with no live `answer` row replying), `consult_fields`.
- `db/queries/run_history_read.py` (397 lines): `_classify_kind` returns `consult` first; a
  parent's window cost adds `AND COALESCE(category, '') != 'consult'`; a consult row's
  `stage_count` defaults to 1; `get_run_detail` adds `run.consults` and `run.waiting_for_person`.
  `_run_outcome` not moved (the file stays under 400).
- `db/queries/chief_session_runs.py`: `record_session_run` deletes the project's rows with
  `read_at` older than 30 days (one `DELETE`, same write lock, before the insert);
  `ended_unread_runs(..., limit=50)` (`LIMIT ?`); `run_notice` carries the consult fields.
- `http_server/blueprints/chief/notices.py`: `limit` (default 50, `int()` of 1 to 200, else 400
  `{"error": "limit must be an integer from 1 to 200"}`); each notice has `consults` and
  `waiting_for_person`.
- `http_server/chief_field_reads.py`: `/chief/notices` lists `keys={"limit": NUMBER}`.
- `supervisor/chief_presets.py`: one Operator bullet on consult runs, notice `consults`, and that
  only `to: human` questions (handed-on ones too) wait for the user; "has no cap of its own"
  shortened to "has no cap" to stay under 4000 (now 3997).
- `src/pathly_orchestrator/CLAUDE.md`: the notices route line and paragraph, the
  `run_consults.py` tree entry, the `GET /runs/<id>` paragraph.
- `tests/http_api/test_chief_notices_consults.py` (new, 8 tests); `tests/INDEX.md`,
  `tests/http_api/INDEX.md` regenerated.

**Proof (fresh, after the last edit)**

- `python -m pytest tests/http_api/test_chief_notices_consults.py -q -p no:cacheprovider`:
  `8 passed`. Covers a `consult-` run listed as `kind: consult` (cost 0.40, own row) and the loop
  parent's cost 0.10 without it; a single run's answered + handed-on routes both in `consults`,
  `waiting_for_person: 1`, another run's route left out; a withheld unanswered route counts and an
  answered hand-on does not; a loop parent shows its two `sched-` tasks' consults and not a third
  run's; no routes gives `[]`/0; a notice equals the detail's `consults` with
  `waiting_for_person: 1`; `limit=2` gives the oldest two of three, `0`, `x`, `201`, `-1`, `2.5`
  are 400 with the exact error, `200` is 200; a row read 31 days ago is deleted, one read
  yesterday, an unread one and another project's old read row stay.
- `python -m pytest tests/http_api/test_chief_cli.py -q -p no:cacheprovider`: `25 passed`.
- `python -m pytest tests/http_api tests/db -q -p no:cacheprovider -k "chief or runs or run_history"`: `2471 passed, 306 deselected`, exit 0.
- Gate key tests (`test_chief_gate_keys.py`, `test_chief_gate_tables.py`,
  `test_chief_gate_kinds.py`): `113 passed`.
- `python3 scripts/check_file_size.py`: `OK: 1075 source files checked; 16 known over 400 lines,
  none new, none grown.` black, mypy (no issues), lint-imports (1 kept, 0 broken), bandit on the
  changed files (none), mirror reads OK, test indexes up to date.

**Decisions**

- `waiting_for_person` is a count; "answered" means a live `answer` row replies to the question
  (as `open_questions_on_board` reads it), not the question's `status`.
- `consults` carries exactly the five ticket keys; the answered check is a second query.
- `limit` uses `int()` on the raw string, so `2.5` and `x` are 400.
- The prune runs on every `record_session_run`, even when the insert is ignored.

**Shortcuts taken**: none.

**For later tickets**

- 10: `GET /runs` rows now have `kind: consult`; Studio can bucket on it.
- 12: the Operator text is at 3997 of 4000 characters; any later addition must shorten something.
