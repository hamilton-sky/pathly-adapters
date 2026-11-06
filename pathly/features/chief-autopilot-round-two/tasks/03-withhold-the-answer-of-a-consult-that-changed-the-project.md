# Withhold the answer of a consult that changed the project

Type: task
Status: open
Blocked by: 02
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/supervisor/consult_run.py, src/pathly_orchestrator/supervisor/consult_window.py (new), tests/runner_supervisor/test_consult_read_only.py (new), src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/runner_supervisor/INDEX.md

A consult is read-only: it may write only under the board's `feedback/` folder, and post board
rows. Measure it instead of trusting it, the way `fsm/gates/reviewer.py::check_reviewer_unchanged`
measures a reviewer: snapshot the git working tree and `HEAD` before and after the spawn
(`snapshot`, `head` and `changes_or_none` in `src/pathly_orchestrator/proof/tree.py`), and when it changed
anything it may not, the answer is not delivered.

New `src/pathly_orchestrator/supervisor/consult_window.py` (new):

- `open_window(project_root) -> Window | None` before the spawn: the tree id, `HEAD`, and the
  declared `files` (`supervisor/task_proof._declared`) of every task `in_progress` on the
  project's boards now.
- `blamed(window) -> list[str] | None` after it: `None` when git cannot snapshot (not a repo top,
  git failed); else the findings: `HEAD moved from <a> to <b>` when it moved, and `<status> <path>`
  for each changed path that is not under the board storage's `feedback/` folder, not one of
  Pathly's own exports (the `pathly/` mirror files `STATE.json`, `BOARD.json`, `EVENTS.jsonl` and
  run storage that `runner/provenance._is_own_storage` already leaves out), and not inside the
  declared `files` of a task `in_progress` at the window's start or at its end (re-read then).

In `start_consult` (ticket 02) fill `_measured_ok`: open the window before the spawn; after it,

- findings → withhold: no answer row and no decision row; route `withheld` with the findings in its
  reason; `hand_to_person(question_id, "the <role> consult changed the project", by=role)`; and an
  `escalation` to `human` (system stamp, `reply_to` the question) listing the findings (at most 20,
  then "... and N more"), saying nothing was reverted and the person decides what to keep, like
  `reviewer.py::_failure_text`. The task stays parked on the question, now a question to the
  person.
- `None` (cannot measure) → deliver as ticket 02 does and post a system `status` reply on the
  question: "answer not measured: <project> is not a git repository top". Fail-open, as the
  reviewer gate does on a read problem.
- no findings → deliver.

## Not in this ticket

- Reverting the consult's change: the person decides (the escalation says so).
- An own worktree per consult, which would make the check exact under concurrent builders: round
  three.

## Done when

- `python -m pytest tests/runner_supervisor/test_consult_read_only.py -q -p no:cacheprovider`
  passes and covers, in a git-initialised temp project with a fake spawn that edits files: a
  consult that edits the temp project's tracked `app.py` gets no answer row, its route is
  `withheld` naming that file,
  its question is `to: human`, one escalation lists the path, and the parked task stays `blocked`;
  one that writes only `<storage>/feedback/NOTES.md` is delivered; one that commits is withheld
  with `HEAD moved`; a change inside the declared `files` of a task `in_progress` during the window
  is left out and the answer delivered; outside a git repo the answer is delivered with the
  "not measured" status reply.
- All existing tests under `tests/runner_supervisor` still pass.

```check
$ python -m pytest tests/runner_supervisor/test_consult_read_only.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/runner_supervisor -q -p no:cacheprovider
exit 0
```

## Reference

- spec.md § Decisions ("What the read-only check blames")
- `src/pathly_orchestrator/fsm/gates/reviewer.py`, `src/pathly_orchestrator/supervisor/spawn_window.py`,
  `src/pathly_orchestrator/supervisor/task_proof.py` (read-only)

## Answer

Work started at `5bab46f9a8aac5ab7f01d3ed8bb0853e37f22ff9` (branch HEAD was the merge `f71e7ab`
on top of it). Test-only commit `22c91ee`: at that commit the Test command fails at collection
(`ImportError: cannot import name 'consult_window'`), the right reason.

**Built**

- `src/pathly_orchestrator/supervisor/consult_window.py` (new, 221 lines): `Window`,
  `open_window(project_root, *, scope=None)`, `blamed(window)`, `withhold(conn, question, role,
  run_id, findings)`, `noted(conn, question, run_id, findings, project_root, status)`.
- `src/pathly_orchestrator/supervisor/consult_run.py` (398 -> 397 lines): `_measured_ok` removed;
  `_run_consult` opens the window before `spawn_fn` (inside the try) and, after the summary is
  parsed, calls `blamed` -> `withhold` on findings, else `_deliver` then `noted`; one docstring
  bullet.
- `tests/runner_supervisor/test_consult_read_only.py` (new, 12 cases).
- `src/pathly_orchestrator/CLAUDE.md`: file-list line for `consult_window.py`; the `_measured_ok`
  bullet of "Consult runs" replaced with the measured read-only rule.
- `tests/INDEX.md`, `tests/runner_supervisor/INDEX.md`: regenerated.

**Proof (fresh, after the last edit)**

- `python -m pytest tests/runner_supervisor/test_consult_read_only.py -q -p no:cacheprovider`:
  `12 passed in 11.92s`, exit 0. Covers: an `app.py` edit -> no
  answer or decision row, route `withheld` with `app.py` in its reason, question `to_agent`
  `human`, one system-stamped `escalation` to `human` listing `M app.py` and "nothing was
  reverted", the parked task still `blocked`; a `<storage>/feedback/NOTES.md` write -> delivered,
  no escalation, no "not measured"; a commit of the feedback file -> withheld, `HEAD moved` in the
  reason and the escalation; 25 new files -> 20 listed, `- ... and 5 more`; a change inside the
  `files` of a task `in_progress` at the start (`app.py`) or claimed during the window (`junk/`)
  -> delivered; outside those files -> withheld; outside a git repo -> delivered with exactly one
  status `answer not measured: <project> is not a git repository top` (system source);
  `blamed(None)` and `open_window(<not a repo>)` are None.
- `python -m pytest tests/runner_supervisor -q -p no:cacheprovider`: `404 passed`, exit 0
  (test_consult_run.py unchanged, 22 passed).
- `python -m pytest tests/comms_board/test_comms_provenance.py -q -p no:cacheprovider`: `106
  passed` (`consult_stamp` still called only in `consult_run.py`; the new posts use
  `provenance.post_system`).
- black `743 files would be left unchanged`; mypy `no issues found in 365 source files`;
  `check_file_size.py` "none new, none grown"; `gen_test_index.py` regenerated then `--check` "All
  test INDEX.md files up to date"; lint-imports 1 kept 0 broken; bandit exit 0;
  `check_no_mirror_reads.py` OK.

**Decisions**

- `open_window` takes an optional `scope` (the question's) so the window knows the board
  storage's `feedback/` folder (`fsm_ops._resolve_storage_path`); the ticket's
  `open_window(project_root)` call still works. Under today's layouts the storage is always under
  `pathly/`, which `_is_own_storage` already leaves out, so the feedback rule matters only for a
  storage outside `pathly/`.
- `blamed` returns the HEAD finding even when the tree diff fails (as the reviewer gate does: a
  moved HEAD needs no diff); None only when nothing could be measured.
- (round 2) The window is measured right after the spawn returns or raises, before `AGENT_DONE`
  and the summary are read, so findings withhold whatever the summary says. With no findings the
  02 failures (spawn raised, no AGENT_DONE, no `ANSWER:` line) fail the route as before. A
  withhold whose route move loses (handed on or answered meanwhile) still posts the escalation,
  because the change is in the project either way; it does not hand on again.
- The "not measured" status is posted only when this consult's own answer row was posted
  (`author_run_id` = the consult run), so an `ANSWER: USER` hand-off or a question answered
  meanwhile gets none, and 02's tests that count status replies keep their counts.
- Route reason: `changed the project: ` + the first 20 findings joined by `; `.

**Shortcuts taken**

- (round 2) "The project's boards" are resolved as `board_mirror.export_project_boards` does:
  the project board whose scope is the normalized root, and a feature board whose
  `pathly/features/<scope>/` folder exists under the root. A same-named feature folder in two
  projects still matches both (the same ambiguity the mirror has; `comms_messages` has no
  project column).
- Concurrent builders whose change is outside every declared footprint withhold the answer (spec
  Decisions, fail-safe); round three's worktree per consult closes it.

**For later tickets**

- 04: unchanged entry point; a consult can now end `withheld` (the question is then to the person).
- 09/10: a `withheld` route has an `escalation` reply to `human` on its question.
- 17: delivery stays in `consult_run._deliver`; `consult_window.withhold` never posts an answer.

**Review fixes (round 1, quality review)** — fix commits after test-only `abe3d5f`.

1. major, cross-project exemptions: `consult_window._in_progress_files(root)` now keeps only
   tasks on this project's boards (`_on_project_board`: project board with scope == the
   normalized root via `board_mirror._norm_project_root`, or a feature board whose
   `pathly/features/<scope>/` is a folder under the root, as `export_project_boards` matches).
   New test `test_another_projects_in_progress_files_do_not_exempt_a_change[feature|project]`:
   another project's in-progress task declares `app.py` and the edit is withheld (failed at
   `abe3d5f`, passes now); `test_an_in_progress_task_on_the_project_board_exempts_its_files`
   guards the project-board match.
2. major, measuring after the summary: `_run_consult` opens the window before the try (it never
   raises), records a raised spawn instead of returning, then runs `blamed` before
   `_agent_done`/`parse_summary`; findings -> `withhold`. New test
   `test_a_consult_that_edits_and_then_fails_is_still_withheld[no-answer-line|raised]`: one
   escalation listing `M app.py`, route `withheld`, question to `human`, task still `blocked`.
   consult_run.py is 400 lines.
3. minor, whole `pathly/` exempt: kept as is. The ticket names `runner/provenance._is_own_storage`
   for the exports and run storage, and that helper's docstring gives the reason a narrower
   prefix breaks: in a project whose `pathly/` was never committed, `git status` collapses the
   untracked tree to `?? pathly/`, so an exports-only rule would blame Pathly's own mirror
   writes on every consult in a fresh project. Narrowing it is a spec change (spec Decisions
   "What the read-only check blames"), not this ticket's.
4. minor, the feedback test cannot fail for its rule alone: noted in the test's docstring that
   it covers both the feedback and the own-storage rule (the reviewer's suggestion while 3
   stands).
5. minor, wording when git fails in a repo: `noted` now says `answer not measured: git could not
   snapshot <project>` when the root is a git top (`proof/tree._is_top`), and keeps the
   ticket's `<project> is not a git repository top` otherwise. New test
   `test_when_git_fails_inside_a_repo_the_status_says_so` (snapshot patched to None).
6. minor, two-way lazy import and private helpers: skipped. Moving `_move`/`_status` into
   `db/queries/consult_routes.py` or renaming `task_proof._declared` /
   `provenance._is_own_storage` changes files outside Touches. Both imports stay lazy (inside
   functions), so there is no import cycle at load time.

**Proof (round 2, fresh after the last edit)**

- `python -m pytest tests/runner_supervisor/test_consult_read_only.py -q -p no:cacheprovider`:
  `18 passed`, exit 0 (5 of them failed at `abe3d5f` for the right reasons).
- `python -m pytest tests/runner_supervisor -q -p no:cacheprovider`: `410 passed`, exit 0.
- `python -m pytest tests/comms_board/test_comms_provenance.py -q -p no:cacheprovider`: `106
  passed`; `consult_stamp` is still called only in `consult_run.py`.
- black `743 files would be left unchanged`; mypy `no issues found in 365 source files`;
  `check_file_size.py` "none new, none grown" (consult_run.py 400, consult_window.py 245);
  `gen_test_index.py` regenerated then `--check` "All test INDEX.md files up to date".

## Review findings (round 1, quality review)

Scope of this pass: ticket 03 read at 5bab46f (cut at ## Answer; the Answer was not read). Code reviewed as `git diff f71e7ab HEAD` (commits 22c91ee + 91a66ea; f71e7ab is a merge of master, not the author's work). 91a66ea is HEAD and the newest commit touching the ticket, so no later commits were left out. Re-ran: test_consult_read_only.py (12 passed), tests/runner_supervisor (404 passed), gen_test_index.py --check (up to date), check_file_size.py (OK, consult_run.py 397 lines). No files left behind. Level 3: I probed the consult agent's own output (its summary, the files it writes, its commits, board rows it can post) and the DB rows read for exemptions.

QUALITY
1. major src/pathly_orchestrator/supervisor/consult_window.py (_in_progress_files): the query reads every in_progress task in the shared ~/.pathly DB, with no board, scope or project filter. The ticket says "every task in_progress on the project's boards". Declared files are repo-relative, and common entries (src/, tests/, app.py, package.json) are the same across projects. So a builder running in an unrelated project exempts the same paths here, and a consult that edits them is delivered unblamed. The spec says the check must fail safe, and this lets real edits through. - Restrict it to the project's boards: the project board (scope == the normalized project_root) plus feature boards resolved under this root, the way board_mirror.export_project_boards matches them, or at least the question's own board/scope plus the project board. Add a test where an in_progress task on another project's board declares app.py and the edit is still withheld.
2. major src/pathly_orchestrator/supervisor/consult_run.py (_run_consult): cw.blamed(window) runs only after the spawn returned, AGENT_DONE was found and parse_summary found an ANSWER: line. Every earlier exit (spawn raised or timed out, no AGENT_DONE or more than one, no ANSWER: line) goes to _fail with no measurement and no escalation. So a consult that edits app.py or commits and then leaves out the ANSWER: line (or crashes) leaves the change in the project, and the person sees only a "failed" route with no word that anything changed. This is the one input the consult controls that skips the read-only check entirely. - Measure right after the spawn, before _agent_done and parse_summary. When there are findings, withhold (route withheld + escalation) whatever the summary says. Otherwise carry on as now. Add a test: a fake spawn that edits app.py and writes a summary with no ANSWER line gets one escalation listing app.py.
3. minor src/pathly_orchestrator/supervisor/consult_window.py (_may_write via runner.provenance._is_own_storage): the whole pathly/ tree is exempt. That covers IMPLEMENTATION_PLAN.md, USER_STORIES.md, ticket text and other boards' feedback and artifacts, which is wider than the spec's "Pathly's own exports". The ticket names _is_own_storage, and floor_gate catches plan and task-text edits in team/goal-loop flows, so I rate this minor. But a consult rewriting the plan goes unreported, and single/drain-dag runs have no floor. It also makes the feedback/ exemption (_feedback) dead code whenever board storage is under pathly/, which it always is today. - Follow-up: exempt only the mirror exports (STATE.json, BOARD.json, EVENTS.jsonl), run storage and the board's own feedback/. Blame other pathly/ edits.
4. minor tests/runner_supervisor/test_consult_read_only.py (test_a_consult_that_writes_only_its_feedback_folder_is_delivered): the feedback folder sits under pathly/, so the test passes even with the feedback rule deleted. It cannot fail for the rule it names. - Once item 3 is narrowed, this test discriminates. Until then, note in the test that it covers both rules.
5. minor src/pathly_orchestrator/supervisor/consult_window.py (blamed/noted): blamed returns None both outside a repo top and when snapshot, head or changes_or_none fails or raises inside a repo. noted then always posts "<project> is not a git repository top", which is wrong in the second case. - Word the status as "answer not measured: git could not snapshot <project>", or carry the reason on the window.
6. minor src/pathly_orchestrator/supervisor/consult_window.py: a two-way lazy import (consult_window imports consult_run._move/_status, and consult_run imports consult_window), plus private helpers taken from three other modules (task_proof._declared, provenance._is_own_storage, fsm_ops._resolve_storage_path). Rule #5 says shared helpers belong in a shared helper module. - Move _move/_status into the consult_routes query module or a supervisor _helpers, and give _declared/_is_own_storage public names.

REVIEW: FAIL

## Review findings (round 2, quality review)

Scope of this pass: quality round 2 of ticket 03. Ticket read cut at ## Answer, plus its "## Review findings (round 1, quality review)" section; the Answer was not read, so any reasons the author gave for declining round 1 items are not known to me. Code reviewed as `git diff f71e7ab HEAD`, and the round 2 fixes as `git diff e612cfb HEAD` (commits abe3d5f and 7c382c9). 7c382c9 is HEAD and the newest commit touching the ticket, so no later commits were left out. Status in the ticket hunk: open -> resolved. Re-ran: test_consult_read_only.py (18 passed), tests/runner_supervisor (410 passed), gen_test_index.py --check (up to date), check_file_size.py (OK). No files left behind, working tree clean.

Round 1 findings:
- 1 (major, in_progress files from every project): fixed. `_in_progress_files(root)` keeps only the project board (scope == normalized root) and feature boards whose `pathly/features/<scope>/` exists under the root. Tests for another project's feature board and project board (both withheld) and for this project's board (exempt) are added and can fail.
- 2 (major, a failed consult was never measured): fixed. `open_window` now runs outside the try, and `blamed` runs right after the spawn returns or raises, before `_agent_done`/`parse_summary`. Findings withhold whatever the summary says. There are parametrized tests for "no ANSWER line" and "spawn raised".
- 3 (minor, all of pathly/ is exempt): not changed. It is still minor.
- 4 (minor, the feedback test cannot fail): handled the way round 1 offered, with a docstring saying the test covers both rules.
- 5 (minor, wrong "not a git repository top" wording): fixed with `_why_unmeasured`, and a test is added.
- 6 (minor, circular lazy import and private helpers): not changed, and now extended (`tree._is_top`). It is still minor.

Level 3 probe: I probed the inputs the consult controls (the board rows and task claims it can make over HTTP, the files it edits, its commits, when it writes AGENT_DONE, whether the spawn returns or raises) and the task rows' `board`/`scope`/`files` read for exemptions.

QUALITY
1. major src/pathly_orchestrator/supervisor/consult_window.py (blamed re-reading _in_progress_files at window end): the consult can exempt its own edits. It runs headless with permissions skipped and can call the server. `/comms/tasks/claim` accepts an anonymous caller with any body `run_id` (tasks_claim.py), and nothing stops a run posting a `type=task` row. So a consult can post (or claim an existing pending) task on its own project or feature board that declares `app.py`, claim it to `in_progress`, and edit `app.py`. The end re-read then adds `app.py` to `window.declared` and the answer is delivered unblamed. Round 2 narrowed the boards, but the question's own board always passes that filter. - At the end, exempt only files of tasks that were already `in_progress` when the window opened, plus tasks claimed during the window by a run other than this consult (`claimed_by` is not this `run_id` and the task row was posted before the window). Anything else counts against the consult, which keeps the fail-safe direction. Add a test where the fake spawn posts and claims a task declaring app.py and then edits it: the answer must still be withheld. If the spec's "re-read at its end" is meant to allow this, that is a question for the architect, not something to leave silent.
2. major src/pathly_orchestrator/supervisor/consult_run.py (_run_consult -> _default_spawn -> terminal._run_stage_via_terminal): the measurement is taken when the spawn returns, but that is not when the consult stops. `PATHLY_RUNNER_EARLY_ADVANCE` defaults to on (feature_flags.py), and then the spawn returns as soon as an AGENT_DONE appears, while the PTY keeps running. On the 1800 s result timeout it raises without killing the process. So a consult that writes its AGENT_DONE first and then edits or commits (or keeps running past the timeout) is measured clean and its answer is delivered. Round 2's "measure right after the spawn" fix also depends on this. - Have the consult spawn wait for the PTY to exit before `blamed` (early advance off for flow `consult`, or wait on the PTY result after an early AGENT_DONE). When the spawn timed out, or the process could not be confirmed stopped, treat the window as unmeasurable and do not deliver silently. Add a test whose fake spawn edits app.py after writing AGENT_DONE, if the seam allows it.
3. minor src/pathly_orchestrator/supervisor/consult_window.py (_on_project_board): the docstring says feature boards are matched "the way board_mirror.export_project_boards matches them", but there is no `is_segment` or reserved-name check (board_mirror_path refuses those). A task row whose feature scope is `../..` or an absolute path makes `Path(norm)/"pathly"/"features"/scope` name any existing folder, so another project's task counts as this project's. - Reuse `board_mirror.board_mirror_path` (None means not this project), or check `is_segment(scope)` first.
4. minor src/pathly_orchestrator/supervisor/consult_run.py: now exactly 400 lines. Ticket 04 (which wires `start_consult`) cannot add a line without splitting first. - Move the delivery helpers (`_deliver`/`_post`/`_fail`) out now, together with round 1 item 6 (`_move`/`_status` into a shared helper, and public names for `_declared`, `_is_own_storage` and now `tree._is_top`).
5. minor src/pathly_orchestrator/supervisor/consult_window.py (_may_write): round 1 item 3 still stands. The whole of `pathly/` is exempt, so a consult that rewrites IMPLEMENTATION_PLAN.md or ticket text goes unreported, and the feedback/ rule is dead code while storage is under pathly/. - Narrow the rule as round 1 said, or record it in followups.md.

REVIEW: FAIL
