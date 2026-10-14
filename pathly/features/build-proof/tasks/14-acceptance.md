# Prove build-proof end to end

Type: task
Status: open
Blocked by: 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 15, 16
Test first: no
Floor: allow skip

Write `tests/fsm_flows/test_build_proof_acceptance.py`. It runs the brief's bar against the real
flows. Setup:

- **Project.** A `git init` project under `tmp_path` with one commit: `src/app.py`,
  `tests/test_app.py` and a `.gitignore` for `pathly/**/BOARD.json` and `EVENTS.jsonl`.
- **FSM.** `fhc.next_action` and `fhc.complete_stage` patched to the in-process
  `fsm_ops.next_action` and `fsm_ops.complete_stage`, as
  `tests/runner_supervisor/test_runner_fsm_integration.py` does.
- **Agents.** `pathly_orchestrator.supervisor._run_stage_via_terminal` patched to one scripted
  fake agent that records every `(run_id, instructions, session)` it gets, and returns
  `session_id` `<run_id>-sess`. It acts by `state.current_state` and run id: it edits files in
  the project, claims and completes board tasks through `claim_task`/`complete_task` as
  `team/build` does, writes `VERIFY.md`, `REVIEW.md` or feedback files, and appends `AGENT_DONE`
  with `run_id` and `summary` through `eventlog.append_event`. A spawn that a scenario does not
  script is a no-op success.
- **Settings.** `code_context.backend` is set to `off` so no code-intel backend starts.
- **Runs.** Through `supervisor.start_run` with the packaged `team-build` and `goal-loop` flows
  and a goal with board tasks, waiting on `state.status` with a deadline.

One test per bar item:

1. **Floor send-back.**
   - team-build: the task declares `files: ["src/app.py", "tests/test_app.py"]`, so only the
     floor gate objects. The first builder spawn adds `@pytest.mark.skip` to
     `tests/test_app.py`. `FLOOR_FAILURES.md` is written, and the next spawn is a builder
     feedback spawn whose instructions name it. That spawn removes the skip, and the run goes
     on.
   - goal-loop, a builder fix round after the drain: `verify.test` is set to
     `python -c "import pathlib,sys; sys.exit(0 if pathlib.Path('src/fixed.txt').exists() else 1)"`
     and one clean task drains. The join's `command_gate test` fails, and the builder feedback
     spawn for `TEST_FAILURES.md` writes `src/fixed.txt` and also adds `@pytest.mark.skip` to
     `tests/test_app.py`. The test command is now green, but `FLOOR_FAILURES.md` is written
     with a `skip:` finding, and the next spawn is a builder feedback spawn whose instructions
     name it. That spawn removes the skip, and the run reaches `done`.
2. **Check fails, retried with real output, then fails (goal-loop).** A task's text has a
   ```check block running `python -c "import sys; print('red-marker'); sys.exit(3)"`, and
   `goal.task_max_attempts` is 2. The fake reports success both times. The second prompt contains
   `red-marker` and `got: exit 3`. The task ends `failed` with an escalation on the board.
   Only the task's fate is asserted, not what the run does next (the join sends
   `INCOMPLETE_TASKS.md` to builder fix rounds, which the fake leaves as no-ops).
3. **Task text or plan edit caught.**
   - goal-loop: the fake changes its own task's `text` in the DB. The next attempt's prompt
     carries a `task-edit` finding.
   - team-build: the builder edits `pathly/features/<f>/USER_STORIES.md`. `FLOOR_FAILURES.md`
     names `plan-edit`.
4. **Reviewer edit fails review (team-build).** The reviewer spawn writes `REVIEW.md`
   (`RESULT: PASS`) and also changes `src/app.py`. The run ends `parked`, `error_kind`
   `human_checkpoint`, with `REVIEWER_CHANGED_FILES.md` and a `to_agent="human"` escalation.
5. **Red base (team-build).** `verify.build` is set to `python -c "raise SystemExit(1)"`. The
   run ends `parked` with `error_kind` `base_red` and a human escalation, and the fake recorded
   0 spawns.
6. **Dependency result (goal-loop).** Task B depends on A. A's fake `AGENT_DONE` summary is
   `A-RESULT-MARKER`, and B's recorded instructions contain it under
   `## Results of the tasks this one depends on`.
7. **Debug fragment on retry.** The second prompt in scenario 2 and the builder feedback prompts
   in scenario 1 all contain `## Root-cause debugging`.
8. **Happy path (team-build and goal-loop).**
   - team-build: one task with a passing ```check block and `files: ["src/app.py"]`. The builder
     edits `src/app.py` and completes the task. The reviewer writes only `REVIEW.md`, and its
     instructions contain `## Review packet` and the task's text, but not the builder's
     `AGENT_DONE` summary. The reviewer spawn was called with `session=None`, although the
     builder spawn returned a session id (it does not resume the builder's conversation). The
     tester and retro write what their gates need. The run reaches `done`.
   - goal-loop: two clean tasks reach `done`, and the run passes the join (`floor_gate` finds
     nothing, `task_checks` runs nothing new) and reaches `done`.

Then the release notes: a `CHANGELOG.md` entry under "Unreleased", in the style of the
role-read-policy entry, whose heading ends in `(build-proof)`. It says what is now measured
(floor guard, checks, frozen task text, scope, reviewer no-change, Review packet), what helps
agents (dependency results, root-cause guide), the run guard rails (smoke, budget), the new
settings and route, and the known limits (spec.md § Risks, map.md § Open questions).

Check every living doc touched by tickets 01 to 13, 15 and 16 against the code once more
(verify-then-fix, do not rewrite). Regenerate the test indexes and run the full suite.

The `Floor:` line above is needed because scenario 1's fake builder writes `@pytest.mark.skip`,
and that line is in this test's source.

## Not in this ticket

- New behaviour: anything the scenarios find missing goes back to the ticket that owns it.
- Studio: no Studio change in this feature.

## Done when

- `python -m pytest tests/fsm_flows/test_build_proof_acceptance.py -q -p no:cacheprovider`
  passes.
- `python -m pytest tests/ -q -p no:cacheprovider` passes in full.
- `python scripts/gen_test_index.py --check` exits 0.
- `CHANGELOG.md` has a `### ... (build-proof)` entry under "Unreleased".

```check
# The conductor runs this block before review.
$ python -m pytest tests/fsm_flows/test_build_proof_acceptance.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/ -q -p no:cacheprovider
exit 0
prints passed
$ python scripts/gen_test_index.py --check
exit 0
$ python -c "import re,pathlib;t=pathlib.Path('CHANGELOG.md').read_text(encoding='utf-8');m=re.search(r'\n## Unreleased\n(.*?)(?=\n## |\Z)',t,re.S);print('found' if m and re.search(r'\n### [^\n]*\(build-proof\)\n',m.group(1)) else 'missing')"
exit 0
prints found
```

## Reference

- map.md (the bar), spec.md § Goal and the bar, § Happy path, § Edge cases
- `tests/runner_supervisor/test_runner_fsm_integration.py` (patching `fhc` and
  `_run_stage_via_terminal`; `test_smart_fix_routing_drives_real_team_flow` drives
  `team.flow.yaml`)
- `tests/fsm_flows/test_golden_path.py` (goal-loop with a fake spawn)
- `tests/conftest.py` (a fresh temporary DB per test; `get_db()` is per thread). Read-only: do
  not edit it.

## Answer
