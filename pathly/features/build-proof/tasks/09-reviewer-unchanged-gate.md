# Fail the review stage when a reviewer spawn changed files or committed

Type: task
Status: resolved
Blocked by: 04
Test first: yes

New gate type `reviewer_unchanged` in `src/pathly_orchestrator/fsm/gates/reviewer.py`, registered
in `fsm/gates/__init__.py::_CHECKS`. It judges only spawns made in the reviewer role. Builder fix
rounds also run inside REVIEWING, and they may change code.

`check_reviewer_unchanged`:

- Find when the run last entered REVIEWING: the newest `STATE_TRANSITION` event with
  `to == "REVIEWING"` in `eventlog.read_events(storage_path)`.
- Take the reviewer windows: `_proof.windows_since(storage_path, since=<that ts>,
  roles={"reviewer"})`.
- For each window, report:
  - `head_before != head_after`: "HEAD moved from <a> to <b> (the reviewer committed)";
  - every path in `proof.tree.changes(root, before, after)` for which
    `_proof.stage_writes(storage, "reviewer")` is false: "<status> <path>".
- Leave out windows whose `run_id` an earlier `reviewer_unchanged` `GATE_FAILED` event already
  reported. The gate only runs once the feedback folder is clear, so a reported window means a
  human resolved that checkpoint.
- No windows, or nothing to report: pass (`gate_skipped` with reason `no_reviewer_window` when
  there were no windows).
- Otherwise `gate_failed(..., extra={"run_ids": [...]})` with `on_fail`
  (`REVIEWER_CHANGED_FILES.md`). The text lists each change and says the reviewer must judge,
  not edit. The human decides whether to keep or revert the changes, then deletes this file and
  resumes the run.

Flows (`team.flow.yaml`, `team-build.flow.yaml`):

- add `{type: reviewer_unchanged, on_fail: REVIEWER_CHANGED_FILES.md}` as the last gate of
  `REVIEWING->TESTING`, and add the key `REVIEWING->BUILDING` with the same gate (spec.md
  § Migration and compatibility);
- add `REVIEWER_CHANGED_FILES: human` to `feedback_routing`;
- add `REVIEWER_CHANGED_FILES` to `feedback_priority` right after `BLOCKED_ON_HUMAN`.

The supervisor's existing human-checkpoint path (the `target == "human"` branch of
`orchestrator_stage._resolve_stage_supervised`: post an escalation, then park with
`human_checkpoint`) does the rest. Add an `_exit_requirement` line in
`fsm_compose_responses.py`: in REVIEWING, change no file except `REVIEW.md` and feedback files,
and do not commit.

Living docs: the gate in `src/pathly_orchestrator/CLAUDE.md`'s gate list. In the root
`CLAUDE.md` "Ground truth" paragraph, name `reviewer_unchanged` as a gate that measures what the
reviewer changed instead of trusting it. Remove the gate count ("Four of the five") if it is
still there, so the paragraph stays true as other gates are added. Verify-then-fix: change only
those claims.

## Not in this ticket

- What the reviewer is given to read (Review packet, no builder summary): ticket 10.
- Undoing the reviewer's changes automatically: a human decides; nothing is reverted.

## Done when

- `python -m pytest tests/fsm_flows/test_reviewer_unchanged_gate.py -q -p no:cacheprovider`
  passes. On a `team-build` feature in a `git init` project under `tmp_path`, with
  `SPAWN_WINDOW` events from `spawn_window.observe`, it covers:
  - a reviewer window that changed `src/app.py` blocks REVIEWING->TESTING with
    `REVIEWER_CHANGED_FILES.md` routed to `human`;
  - a reviewer window that only wrote `REVIEW.md` and `feedback/REVIEW_FAILURES.md` passes;
  - a reviewer window with a new commit blocks;
  - a builder window inside REVIEWING that changed `src/app.py` passes;
  - after the file is removed, the same window is not reported again;
  - REVIEWING->BUILDING is blocked the same way.
- `python -m pytest tests/runner_supervisor/test_runner_fsm_integration.py -q -p no:cacheprovider`
  still passes.
- The root `CLAUDE.md` names `reviewer_unchanged` and no longer counts the gates. The command
  below prints `docs current`.

```check
# The conductor runs this block before review.
$ python -m pytest tests/fsm_flows/test_reviewer_unchanged_gate.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/runner_supervisor/test_runner_fsm_integration.py -q -p no:cacheprovider
exit 0
prints passed
$ python -c "import pathlib;r=' '.join(pathlib.Path('CLAUDE.md').read_text(encoding='utf-8').split());print('docs current' if 'reviewer_unchanged' in r and 'Four of the five' not in r else 'docs stale')"
exit 0
prints docs current
```

## Reference

- spec.md § Decisions ("What a reviewer may not change"), § Edge cases
- `/home/claude/hamilton-sky/feature-flow/feature_flow/conductor.py::judge_review` (read-only)
- `src/pathly_orchestrator/supervisor/orchestrator_stage.py` (the `target == "human"` branch)
- `src/pathly_orchestrator/fsm/gates/_helpers.py::gate_failed` (`extra`)

## Answer

Work started at commit `789c504ce07f0cb2fd9ea3b1f31bc669f6dbb3ce`. Test-only commit: `f8334e0`
(`test(build-proof): 09 failing test`). At that commit
`python -m pytest tests/fsm_flows/test_reviewer_unchanged_gate.py -q -p no:cacheprovider` exits 1 with
`17 failed, 3 passed` (the 3 that pass are the "reviewer only wrote its own files" style cases that
hold with no gate at all). Every failure is because the packaged flows carry no `reviewer_unchanged`
gate yet (`KeyError`/`assert None == {'gate_failed': 'reviewer_unchanged', ...}`), not an import error.

**Built**

- `src/pathly_orchestrator/fsm/gates/reviewer.py` (new, 152 lines): `check_reviewer_unchanged`.
  It finds the `ts` of the newest `STATE_TRANSITION` with `to == "REVIEWING"` in
  `eventlog.read_events`, takes `_proof.windows_since(storage, since, roles={"reviewer"})`, drops
  windows an earlier `reviewer_unchanged` `GATE_FAILED` named in `run_ids`, and per window reports
  `HEAD moved from <a> to <b> (the reviewer committed)` and every `tree.changes_or_none(root,
  before, after)` path `_proof.stage_writes(storage, "reviewer")` does not allow as
  `<status> <path>`. A finding calls `gate_failed(..., extra={"run_ids": [...]})`; the text lists
  each change, says the reviewer must judge and not edit, and that the human decides, deletes the
  file and resumes.
- `src/pathly_orchestrator/fsm/gates/__init__.py`: registered in `_CHECKS`, plus one row in the
  module docstring's gate table.
- `src/pathly_data/core/flows/team.flow.yaml`, `team-build.flow.yaml`: `reviewer_unchanged`
  (`on_fail: REVIEWER_CHANGED_FILES.md`) as the last gate of `REVIEWING->TESTING`; a new
  `REVIEWING->BUILDING` key holding only that gate; `REVIEWER_CHANGED_FILES: human` in
  `feedback_routing`; `REVIEWER_CHANGED_FILES` in `feedback_priority` right after
  `BLOCKED_ON_HUMAN`.
- `src/pathly_orchestrator/fsm_compose_responses.py`: an `_exit_requirement` branch for
  `reviewer_unchanged` ("In REVIEWING, change no file except `REVIEW.md` and feedback files, and do
  not commit ..."), added once even though two edges carry the gate.
- Docs: root `CLAUDE.md` "Ground truth" paragraph (names `reviewer_unchanged`, "Four of the five"
  removed, no count left); `src/pathly_orchestrator/CLAUDE.md` gate table row, a sentence after the
  table, and a "Reviewer gate" paragraph after the scope gate's limits.
- Tests: `tests/fsm_flows/test_reviewer_unchanged_gate.py` (new, 398 lines, 20 cases), regenerated
  `tests/INDEX.md` and `tests/fsm_flows/INDEX.md`; one existing expectation updated, see Decisions.

**Proof** (each run fresh after the last edit)

- `python -m pytest tests/fsm_flows/test_reviewer_unchanged_gate.py -q -p no:cacheprovider`:
  `20 passed in 7.13s`, exit 0. Each case records windows with the real `spawn_window.observe` in a
  `git init` repo under `tmp_path` and runs the packaged `team-build` flow through the real
  `run_gates`:
  - a reviewer window that edited `src/app.py`, added `src/new.py` and deleted `src/other.py` (and
    wrote `REVIEW.md`) blocks `REVIEWING->TESTING` with `{'gate_failed': 'reviewer_unchanged',
    'feedback_file': 'REVIEWER_CHANGED_FILES.md'}`; the file lists `M src/app.py`, `A src/new.py`,
    `D src/other.py` and not the `REVIEW.md` the window wrote; the `GATE_FAILED` event carries
    `run_ids == ["demo-1-a"]`; `route_feedback` gives `target_agent == "human"`;
  - a window that only wrote `REVIEW.md` and `feedback/REVIEW_FAILURES.md` passes on both edges;
  - a window whose spawn ran `git commit` blocks, and the text holds `HEAD moved from <old> to
    <new>` with the two real shas and `the reviewer committed`;
  - a builder window inside REVIEWING that changed `src/app.py` passes on both edges; with a builder
    and a reviewer window in the same pass only the reviewer's path is named;
  - after `unlink()` of the feedback file the same window is not reported again on either edge (one
    `GATE_FAILED` event in all); a later reviewer window (`demo-2-c`) is reported and only it is
    named, events show `[["demo-1-a"], ["demo-2-c"]]`;
  - `REVIEWING->BUILDING` is blocked the same way (event `transition == "REVIEWING->BUILDING"`);
  - a window before the newest entry into REVIEWING is not judged; no reviewer window passes with a
    `GATE_SKIPPED` of reason `no_reviewer_window`; a project outside git records no window and
    passes; `_proof.windows_since` raising skips with `windows_unreadable`; a tree diff git cannot
    make skips with `git_diff_failed`, while a moved `HEAD` still blocks;
  - both packaged flows carry the gate last on both edges, route `REVIEWER_CHANGED_FILES` to
    `human` and rank it right after `BLOCKED_ON_HUMAN`; the REVIEWING exit requirement says "do not
    commit" once;
  - the real `fsm_ops.complete_stage` on `team-build` returns `blocked`, `decision: escalate`,
    `target_agent: human`, `file: REVIEWER_CHANGED_FILES.md`, state still `REVIEWING`, with the
    change in `instructions`; after the file is removed it returns `next_state == "TESTING"`.
  Two mutations made the right cases fail and were reverted: dropping the "already reported" filter
  failed 3 cases, and widening `roles` to include the builder failed 3.
- `python -m pytest tests/runner_supervisor/test_runner_fsm_integration.py -q -p no:cacheprovider`:
  `5 passed in 2.17s`, exit 0 (its `REVIEWING->TESTING` step now also runs the new gate, which
  skips: no window in a non-git project).
- The docs command prints `docs current`, exit 0.
- Test (`python -m pytest tests/ -q -x -p no:cacheprovider`): `2591 passed, 14 skipped, 1 warning in
  450.29s`, exit 0. (The first full run stopped on the test named in Decisions; this is the rerun
  after that fix.)
- Lint (the full chain in `commands.md`): exit 0. black `508 files would be left unchanged`; mypy
  `Success: no issues found in 287 source files`; file size `947 source files checked; 19 known over
  400 lines, none new, none grown`; mirror reads OK; `All test INDEX.md files up to date.`;
  lint-imports `Contracts: 1 kept, 0 broken.`; bandit reported no issues; adapters OK; entry points
  OK.
- Smoke: exit 0. Build (`python -m build --wheel`): `Successfully built
  pathly_adapters-2.24.1-py3-none-any.whl`, exit 0.

**Decisions**

- `tests/dag_goals/test_flow_decompose.py::test_team_and_test_flows_declare_feedback_priority`
  pinned `team`'s `feedback_priority` to exactly the eight canonical names, so the entry this
  ticket requires made it fail. I changed its expectation, not its strictness: `team` is now
  compared with the canonical list plus `REVIEWER_CHANGED_FILES` inserted at index 2; `test` is
  compared with the unchanged canonical list. This test is not named in the ticket, so a reviewer
  should look at it.
- A window is named in `GATE_FAILED.run_ids` by its `run_id`, falling back to its event `seq` when
  the `run_id` is empty. Without the fallback a window with no `run_id` could never be excluded and
  the human could never get past the checkpoint. Production windows always have a `run_id`.
- With no `STATE_TRANSITION` into REVIEWING in the log, `since` is `None` and every reviewer window
  counts (a run that started in REVIEWING).
- When some windows cannot be diffed and none of the others has a finding, the gate skips with
  `git_diff_failed`; when a finding exists it fails and the unreadable window goes unmentioned.
  A moved `HEAD` is read from the window event, so it needs no git call.
- The failure text names at most 20 lines then a count, like `scope_gate`. It says a reviewer may
  write only `REVIEW.md` and its feedback files and must not commit.
- `_exit_requirement` appends the rule once (`if rule not in lines`): both edges carry the gate, and
  a line per edge would repeat it.
- The orchestrator `CLAUDE.md` sentence "The first four read state that agents produced ..." is
  still true, so I kept it and added one sentence saying `reviewer_unchanged` reads what the
  supervisor measured. The packaged `team.flow.yaml` comments explain the gate in place.
- The gate reads the event log twice (once for the entry stamp and reported windows, once inside
  `windows_since`) rather than re-implementing `windows_since`.

**Shortcuts taken**

- A reviewer window from before the run last entered REVIEWING is never judged. That holds while
  every exit from REVIEWING runs the gate (both edges do in `team` and `team-build`). A flow with
  another exit edge, or a gate failure that goes unreported, would let such a window through; the
  fix is to judge every reviewer window not yet reported, not only the newest pass.
- No window means a skip: an interactive `/pathly` run, or a project that is not a git repo top,
  records none, so the reviewer is not checked there. Same limit as `scope_gate`.
- The window's closing snapshot is taken at the reviewer's `AGENT_DONE` under early advance, so a
  write after its completion report can land outside the window (spec § Risks).

**For later tickets**

- Tickets 06 and 07 add `floor_gate` and `task_checks` to `REVIEWING->TESTING`: insert them
  before `reviewer_unchanged`, which this ticket's test pins as the last gate on that edge (spec §
  Migration order: the existing gates, `floor_gate`, `task_checks`, `reviewer_unchanged`).
  `REVIEWING->BUILDING` carries only `reviewer_unchanged`.
- Ticket 14 (acceptance, "a reviewer that edits a tracked file fails the review stage"): through
  `fsm_ops.complete_stage` the block is `blocked: true`, `decision: escalate`, `target_agent:
  human`, `file: REVIEWER_CHANGED_FILES.md`; the supervisor's `target == "human"` branch posts the
  escalation and parks with `human_checkpoint`. The window only exists if the spawn went through
  `spawn_window.observe` (`reviewer_unchanged` is already in `spawn_window.WINDOW_GATES`).
- `team/review.md` (interactive section "Feedback routing after reviewer") tells the reviewer to
  spawn `po`/`planner`/`architect`/`designer` sub-agents that edit the plan files. The headless
  runner contract says to ignore that, but a sub-agent that did run would write inside the reviewer
  window and fail this gate (plan files are not in the reviewer's write set). Ticket 10, which
  edits `team/review.md`, should not reintroduce a headless path that does that.
- After a human deletes the file and resumes (`POST /runner/resume-parked`), REVIEWING runs a new
  reviewer spawn; its window is judged on its own, and the window the human resolved stays excluded
  by its `run_id`.
