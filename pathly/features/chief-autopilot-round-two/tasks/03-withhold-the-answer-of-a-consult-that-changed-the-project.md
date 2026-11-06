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
