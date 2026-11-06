# Withhold the answer of a consult that changed the project

Type: task
Status: resolved
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
