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
- Withholding runs after the summary is parsed (no AGENT_DONE or no `ANSWER:` line still fails
  the route as in 02). A withhold whose route move loses (handed on or answered meanwhile) still
  posts the escalation, because the change is in the project either way; it does not hand on again.
- The "not measured" status is posted only when this consult's own answer row was posted
  (`author_run_id` = the consult run), so an `ANSWER: USER` hand-off or a question answered
  meanwhile gets none, and 02's tests that count status replies keep their counts.
- Route reason: `changed the project: ` + the first 20 findings joined by `; `.

**Shortcuts taken**

- "Every task `in_progress` on the project's boards" reads every in-progress task in the DB:
  `comms_messages` has no project column. Exempting another project's declared files can only
  leave a change unblamed when the paths coincide; a project column (or board -> project map)
  would make it exact.
- The not-measured text always says "is not a git repository top", also when git itself failed
  (the ticket's wording).
- Concurrent builders whose change is outside every declared footprint withhold the answer (spec
  Decisions, fail-safe); round three's worktree per consult closes it.

**For later tickets**

- 04: unchanged entry point; a consult can now end `withheld` (the question is then to the person).
- 09/10: a `withheld` route has an `escalation` reply to `human` on its question.
- 17: delivery stays in `consult_run._deliver`; `consult_window.withhold` never posts an answer.

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
