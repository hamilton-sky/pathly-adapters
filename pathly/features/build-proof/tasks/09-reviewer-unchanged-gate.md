# Fail the review stage when a reviewer spawn changed files or committed

Type: task
Status: open
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
