# Put dependency results in task prompts and the root-cause guide in retry prompts

Type: task
Status: open
Blocked by: —
Test first: yes

**Dependency results.** A DAG task never sees what the tasks it depends on produced. Add
`src/pathly_orchestrator/db/queries/task_results.py::latest_task_summaries(conn, task_ids) ->
dict[str, str]`. For each id it reads the newest `AGENT_DONE` in `fsm_events` whose payload
`run_id` is `sched-<id>#<n>`: one fixed query with
`json_extract(payload, '$.run_id') LIKE ?` and `ORDER BY seq DESC LIMIT 1`, passing
`sched-<id>#%` as a parameter. It returns that payload's `summary`. `supervisor/terminal.py`
already substitutes `<run_id>` with the spawn's run id, so a task agent's `AGENT_DONE` carries
it.

In `supervisor/task_prompt.build_task_prompt`, after the task body and before the runner
contract, add `## Results of the tasks this one depends on`. It has one `### ` heading per
direct `depends_on` id (the dependency's first text line), followed by its summary, or
`(no result recorded)`. Clip each summary to 2000 characters and the whole block to 8000. A task
without `depends_on` gets no block, so its prompt is unchanged.

In `src/pathly_data/core/skills/development/execute-task.md`, ask for a completion summary that
says what was built, which files changed, any shortcut taken, and anything a later task needs to
know, because dependent tasks read it.

**Root-cause guide.** Add `src/pathly_data/core/skills/fragments/root-cause-debug.md`, ported from
`/home/claude/hamilton-sky/feature-flow/guides/debug.md` (MIT), with heading
`## Root-cause debugging`. Do not use the words "Retry attempt": `tests/fsm_flows/test_retry_ladder.py`
looks for them. Its steps:

1. read every failure above;
2. reproduce it with the exact command;
3. isolate the cause;
4. fix the cause, never weakening a check: no skipped or deleted tests, no loosened
   expectations, no silenced linters, no edits to lint, test or CI config, and say that the
   supervisor's floor guard checks this;
5. prove it by re-running the failing command and the task's checks.

Stop after two failed fixes of the same error, and report what was tried instead of trying a
third time.

Read it at runtime through `skills/compose_resources._read_fragment` (or a small public wrapper
next to it). It is not added to `composition.yaml`, so no golden snapshot changes. Append it:

- in `supervisor/task_retry.build_retry_context`, after the failure block. That block exists only
  from the second attempt on, so a first attempt's prompt stays byte-identical;
- in `fsm_compose.build_prompt_for_agent`, when `agent_name == "builder"` and a `feedback_file`
  is given. Every builder feedback prompt is a second attempt at the stage, and the FSM
  `retry_count` never climbs in headless runs (spec.md § Decisions, map.md § Open questions).

Living docs: the fragment in the fragment list of `src/pathly_data/CLAUDE.md`. In
`src/pathly_orchestrator/CLAUDE.md`, the dependency-results block and where the guide is
appended.

## Not in this ticket

- Making the FSM `retry_count` climb in headless runs: an open question, not this feature.
- Results of indirect (transitive) dependencies: only direct `depends_on`, as the brief says.

## Done when

- `python -m pytest tests/dag_goals/test_dependency_results.py -q -p no:cacheprovider` passes. It
  covers:
  - with an `AGENT_DONE` for `sched-<A>#1` whose summary is `A-RESULT-MARKER`, the prompt of B
    (`depends_on: [A]`) contains the heading and the marker;
  - a later `sched-<A>#2` summary wins;
  - a task without dependencies has no heading;
  - a dependency with no event shows `(no result recorded)`.
- `python -m pytest tests/dag_goals/test_retry_debug_guide.py -q -p no:cacheprovider` passes. It
  covers:
  - `build_retry_context` for a first attempt is empty;
  - for a second attempt with a `fail_reason` it contains `## Root-cause debugging`;
  - `build_prompt_for_agent("builder", storage, feedback_file="REVIEW_FAILURES.md")` contains it;
  - the same call for `planner`, and `builder` without a feedback file, do not.
- `python -m pytest tests/fsm_flows/test_retry_ladder.py tests/dag_goals/test_task_retry.py -q -p no:cacheprovider`
  still passes.

```check
# The conductor runs this block before review.
$ python -m pytest tests/dag_goals/test_dependency_results.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/dag_goals/test_retry_debug_guide.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/fsm_flows/test_retry_ladder.py tests/dag_goals/test_task_retry.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- spec.md § Decisions ("When the debug guide is added", "Where dependency results come from")
- `src/pathly_orchestrator/supervisor/task_prompt.py::build_task_prompt`,
  `supervisor/task_retry.py::build_retry_context`,
  `fsm_compose.py::build_prompt_for_agent`, `skills/compose_resources.py::_read_fragment`
- `/home/claude/hamilton-sky/feature-flow/guides/debug.md` (read-only; MIT)

## Answer
