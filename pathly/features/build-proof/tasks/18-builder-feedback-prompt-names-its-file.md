# Name the feedback file, and show its text, in a feedback spawn's prompt

Type: task
Status: open
Blocked by: —
Test first: yes

When a gate writes a feedback file that a flow routes to a role (`FLOOR_FAILURES.md`,
`TASK_CHECK_FAILURES.md`, `BUILD_FAILURES.md`, `TEST_FAILURES.md`, `INCOMPLETE_TASKS.md`,
`REVIEW_FAILURES.md`, ...), the supervisor runs a feedback spawn whose prompt is
`fsm_compose.build_prompt_for_agent(agent, storage_path, feedback_file=..., retry_count=...)`.
That prompt names the file and shows its text in only two cases:

- the retry ladder (`_retry_ladder_block`), from `retry_count > 0`. A headless run never writes
  `retry_count_by_key` to STATE, so `route_feedback` always returns `retry_count` 0 and the ladder
  never appears;
- the Fix mode block, for the four roles in `_FIX_MODE_ARTIFACT` (po, planner, architect,
  designer).

So a builder, a reviewer or a tester sent back gets its agent text, `## Current task`,
`Feature:` and `Storage path:`, and for a builder the `## Root-cause debugging` guide, whose
first step says "Read every failure above". Nothing is above it. The file sits in
`<storage>/feedback/` when the agent starts, but the prompt never says so. The acceptance test
found it (`assert_sent_back`: it can only check the storage path and the `feedback/` listing).

**The change.** A new module `src/pathly_orchestrator/fsm_compose_feedback.py` (`fsm_compose.py`
is 386 lines and must stay at or under 400) holds:

- `read_feedback(storage_path, feedback_file) -> str`: the file's text, stripped, clipped to
  4000 characters, `""` when it cannot be read. `_retry_ladder_block` calls it instead of its
  inline read, so there is one rule for what a prompt shows of a feedback file;
- `feedback_block(storage_path, feedback_file) -> str`: a `## Feedback to resolve` section that
  names the file by the same path the Fix mode block uses (`<storage>/feedback/<file>`), says it
  is what the gate or reviewer wrote and that the cause, not the file, is to be fixed, and shows
  the text in a code fence one backtick longer than any run of backticks inside it (these files
  quote failing command output, which can hold a triple backtick; the Review packet in
  `fsm_compose_review.py` has the same rule). When the text cannot be read the block still names
  the file and says so.

`build_prompt_for_agent` appends the block when `feedback_file` is given, `retry_count == 0` and
`agent_name` is not in `_FIX_MODE_ARTIFACT`: right after the `## Current task` context and
before the Fix mode block and the root-cause guide, so "Read every failure above" is true. From
`retry_count > 0` the ladder already carries the text, so the block is not added a second time
(the text appears once). A call with no `feedback_file`, and a fix-mode role, are byte-identical
to before.

All three callers get it through the one function (`fsm_ops_complete` twice, `fsm_ops.next_action`
once); change none of them.

**Tests that pin the old prompt change on purpose** (round 1 of a builder, reviewer or tester is
no longer byte-identical): `tests/fsm_flows/test_retry_ladder.py` (round 1 is "untouched"),
`tests/fsm_flows/test_fix_routing.py` (`test_build_prompt_for_agent_builder_path_unchanged`,
`test_build_prompt_for_agent_reviewer_and_human_never_get_fix_mode`), and whatever else fails in
`tests/fsm_flows`, `tests/dag_goals` and `tests/runner_supervisor` after the change. Update each
to pin the new prompt (the block is there, in that place, once); do not loosen an assertion to
make it pass. In `tests/fsm_flows/test_build_proof_acceptance.py`, `assert_sent_back` now also
asserts that the instructions contain `## Feedback to resolve` and the feedback file's name, and
its docstring drops the sentences saying the prompt does not name the file.

New tests go in `tests/fsm_flows/test_feedback_prompt_names_file.py`:

1. a builder, `FLOOR_FAILURES.md` with text, round 1: the prompt has the block with the path and
   the text, and the block comes before `## Root-cause debugging`;
2. the same for a reviewer (`REVIEW_INCOMPLETE.md`) and a tester: the block is there, no guide;
3. `retry_count=1`: the text appears once (in the ladder), and there is no `## Feedback to
   resolve`;
4. a po/planner/architect/designer role with a feedback file: no new block (Fix mode as before);
5. no feedback file: unchanged;
6. a file that does not exist: the block names it and says it could not be read, no crash;
7. a 6000-character file is clipped to 4000, and a file that contains a triple backtick is
   fenced with four.

Living docs, same change: the "Retry ladder" section of `src/pathly_orchestrator/CLAUDE.md`
(what a round-1 feedback prompt carries, and the sentence on the root-cause guide's position),
the `fsm_compose` row of the split-modules table (`fsm_compose_feedback`), and the "Known
limits" paragraph of the build-proof entry in `CHANGELOG.md` (remove "a builder feedback prompt
does not name the feedback file it is handed"; the retry-ladder half of that sentence stays).

## Not in this ticket

- Writing `retry_count_by_key` in headless runs, or any change to `escalation_routing`: that
  changes escalation behaviour (map.md § Open questions, first item).
- The retry ladder's `history` block still listing `AGENT_DONE` summaries.
- The DAG-task prompt (`task_retry.build_retry_context`): it already shows the failure.

## Done when

- `python -m pytest tests/fsm_flows/test_feedback_prompt_names_file.py -q -p no:cacheprovider`
  passes.
- `python -m pytest tests/fsm_flows tests/dag_goals tests/runner_supervisor -q -p no:cacheprovider`
  passes (the updated tests and the acceptance test included).
- `python scripts/check_file_size.py` exits 0 and `python scripts/gen_test_index.py --check`
  exits 0.
- The stale sentence is gone from `CHANGELOG.md`.

```check
# The conductor runs this block before review.
$ python -m pytest tests/fsm_flows/test_feedback_prompt_names_file.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/fsm_flows tests/dag_goals tests/runner_supervisor -q -p no:cacheprovider
exit 0
prints passed
$ python scripts/check_file_size.py
exit 0
$ python scripts/gen_test_index.py --check
exit 0
$ python -c "import pathlib;t=pathlib.Path('CHANGELOG.md').read_text(encoding='utf-8');print('clean' if 'does not name the feedback file it is handed' not in t else 'still there')"
exit 0
prints clean
```

## Reference

- `src/pathly_orchestrator/fsm_compose.py` (`build_prompt_for_agent`, `_retry_ladder_block`),
  `fsm_compose_tables.py` (`_FIX_MODE_ARTIFACT`), `fsm_compose_review.py` (the fence rule),
  `skills/compose_resources.py` (`root_cause_guide`), `skills/fragments/root-cause-debug.md`
- `src/pathly_orchestrator/fsm_ops_complete.py` and `fsm_ops.py` (the callers),
  `fsm/engine_transitions.py` (`route_feedback`, `retry_count`)
- `tests/fsm_flows/test_retry_ladder.py`, `tests/fsm_flows/test_fix_routing.py`,
  `tests/fsm_flows/test_build_proof_acceptance.py` (`assert_sent_back`)
- map.md § Open questions (the last item), learnings.md (14)

## Answer
