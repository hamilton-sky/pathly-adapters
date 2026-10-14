# Put dependency results in task prompts and the root-cause guide in retry prompts

Type: task
Status: resolved
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

**Built**

- `src/pathly_orchestrator/db/queries/task_results.py` (new): `latest_task_summaries(conn, task_ids) -> dict[str, str]`. One fixed query per id: newest `AGENT_DONE` (`ORDER BY seq DESC LIMIT 1`) whose `json_extract(payload, '$.run_id') LIKE 'sched-<id>#%'` (passed as a parameter), returning its `summary`. An id with no event, or a newest event with no summary, is left out of the dict.
- `src/pathly_orchestrator/supervisor/task_dependencies.py` (new): `dependency_results_block(task)`. Reads the task's direct `depends_on` (JSON string or list), and returns `"\n\n## Results of the tasks this one depends on"` + one `### <dependency's first text line>` heading per id (in `depends_on` order, no repeats) followed by its summary clipped to 2000 characters or `(no result recorded)`; the whole block is clipped to 8000. A task without `depends_on`, or one whose results cannot be read (any exception, logged at debug), gets `""`, so its prompt is unchanged.
- `src/pathly_orchestrator/supervisor/task_prompt.py`: `build_task_prompt` appends that block after the task body and before the runner contract (3 lines, plus the docstring's layer list).
- `src/pathly_data/core/skills/fragments/root-cause-debug.md` (new): `## Root-cause debugging`, ported from `/home/claude/hamilton-sky/feature-flow/guides/debug.md` (MIT) as a five-step list (read every failure above, reproduce with the exact command, isolate, fix the cause never weakening a check and naming the supervisor's floor guard, prove by re-running the failing command and the task's checks) plus the stop-after-two-failed-fixes rule. It does not contain "Retry attempt". Not added to `composition.yaml`.
- `src/pathly_orchestrator/skills/compose_resources.py`: `root_cause_guide()`, the small public wrapper next to `_read_fragment`; returns the stripped fragment, or `""` plus a logged warning on `OSError`.
- `src/pathly_orchestrator/supervisor/task_retry.py`: `build_retry_context` appends the guide after the failure block (a first attempt still returns `""`).
- `src/pathly_orchestrator/fsm_compose.py`: `build_prompt_for_agent` appends the guide when `agent_name == "builder"` and `feedback_file` is given (+6 lines, now 388).
- `src/pathly_data/core/skills/development/execute-task.md`: one bullet asking for a completion summary that says what was built, which files changed, any shortcut taken and anything a later task needs to know, because dependent tasks read it.
- Docs: `src/pathly_data/CLAUDE.md` (the fragment, outside `composition.yaml`); `src/pathly_orchestrator/CLAUDE.md` (module map entries, the prompt-assembly diagram, a paragraph in "Retry ladder" on the builder feedback prompt, and the guide plus a "Dependency results" paragraph in "Phase 1: per-task retry").
- Tests: `tests/dag_goals/test_dependency_results.py` (17 tests) and `tests/dag_goals/test_retry_debug_guide.py` (19 tests), committed first (`8047975`, failing: 22 of 36 failed for the missing block, module and fragment). `tests/fsm_flows/test_fix_routing.py::test_build_prompt_for_agent_builder_path_unchanged` changed, see Decisions.

**Proof**

All run fresh after the last edit, in `/home/claude/pathly-adapters` with the dev venv on PATH.

- `python -m pytest tests/dag_goals/test_dependency_results.py -q -p no:cacheprovider`: `17 passed`, exit 0. Covers the four listed cases (B's prompt has the heading and `A-RESULT-MARKER`; a later `sched-<A>#2` summary wins and the `#1` summary is absent; a task without dependencies, and one with `depends_on: []`, has no heading; a dependency with no event shows `(no result recorded)`), plus: an event without a summary, direct dependencies only, one heading per dependency in `depends_on` order, the 2000 and 8000 clips, an unreadable `depends_on`, block placement between the task and the runner contract, `latest_task_summaries` (newest per id, `AGENT_DONE` only, other runs ignored, empty input) and the `execute-task` wording.
- `python -m pytest tests/dag_goals/test_retry_debug_guide.py -q -p no:cacheprovider`: `19 passed`, exit 0. Covers: first attempt gives `""`; second attempt with a `fail_reason` contains `## Root-cause debugging` after the failure; `build_prompt_for_agent("builder", storage, feedback_file="REVIEW_FAILURES.md")` contains it (once, also with `retry_count=1`); `planner`, `architect`, `po`, `designer`, `reviewer`, and `builder` without a feedback file, do not; a missing fragment file leaves the failure block intact; a retried DAG task prompt has the guide and a first attempt does not; the fragment's steps, no-weakening words, floor guard, stop rule, and that it is not in `composition.yaml`.
- `python -m pytest tests/fsm_flows/test_retry_ladder.py tests/dag_goals/test_task_retry.py -q -p no:cacheprovider`: `36 passed`, exit 0.
- Beyond Done when: the full Test command `python -m pytest tests/ -q -x -p no:cacheprovider` gave `2655 passed, 14 skipped in 445.62s`, exit 0 (the 14 skips are not mine); the Lint chain from `commands.md` exits 0 (black 517 files unchanged, mypy no issues in 290 files, `check_file_size.py` "none new, none grown", `lint-imports` 1 contract kept, bandit, `gen_test_index.py --check`, `check_adapters.py`, `check_entry_points.py`); the Smoke imports exit 0; `python -m build --wheel` exits 0 and the wheel holds `root-cause-debug.md`, `task_results.py` and `task_dependencies.py`; `python3 scripts/floor-guard.py build-proof 11 950d714...` printed `floor guard: clean`.

**Decisions**

- The dependency block's code is in a new `supervisor/task_dependencies.py`, not inside `task_prompt.py`: one concern per file, and `build_task_prompt` grows by three lines. The ticket names `build_task_prompt` as the place the block is added, and it still is.
- `latest_task_summaries` also filters `event_type='AGENT_DONE'` (the ticket's query names only the `run_id` match): a `BILLING_UPDATE` or other event carrying the same `run_id` must not be read as a result. A test pins it.
- Clips end in an ellipsis inside the limit (a 2000-character summary becomes 1999 characters + `…`), so the agent can see it was cut and the limits are exact.
- A dependency heading is its first non-blank text line, clipped to 200 characters; a dependency row that cannot be read falls back to its id.
- `root_cause_guide()` swallows `OSError` and logs a warning: `build_task_prompt` runs on a scheduler worker thread outside any try, so an unreadable fragment must cost the guide, not kill the worker. Both callers append only a non-empty guide.
- **Changed an existing test.** `tests/fsm_flows/test_fix_routing.py::test_build_prompt_for_agent_builder_path_unchanged` asserted that a builder prompt is byte-identical with and without `feedback_file`, which is the exact behaviour this ticket changes (the full `-x` run stopped there). I kept the test name and its exact-equality strength: it now asserts `with_feedback == without_feedback + "\n" + root_cause_guide() + "\n"` (nothing else added) and still asserts there is no "Fix mode". The ticket's own Done when does not list this test. A reviewer should confirm this reading; the floor guard reports clean.
- Dependency lookups are by `sched-<id>#%`, as the ticket says. `LIKE` treats `_` and `%` in an id as wildcards; task ids are uuid4 (hex and hyphens), so no real id contains one.

**Shortcuts taken**

- Each dependency is one query that scans `fsm_events` newest-first (there is no index on `event_type` or `run_id`; `EXPLAIN QUERY PLAN` shows `SCAN fsm_events`). Cheap while the dependency has run recently, a full scan when it has no result. It stops being fine on a very large event table with many dependency-less lookups; the upgrade is an index on the `run_id` expression, or the result column the spec rejected, once it shows up in a profile.
- Only the newest `AGENT_DONE`'s summary is used: if the last attempt wrote no summary, an older attempt's summary is not used and the dependency shows `(no result recorded)`.

**For later tickets**

- Ticket 14 (acceptance) can check the dependent-task prompt and the retry prompt through `supervisor.task_prompt.build_task_prompt`; the heading strings are `## Results of the tasks this one depends on` and `## Root-cause debugging`. A task's `AGENT_DONE` must carry `run_id: sched-<id>#<n>`, which the real `completion-report` fragment does once `terminal.py` substitutes `<run_id>`; a scripted fake agent has to write that `run_id` itself.
- Ticket 05 (goal-loop per-task proof) retries through `task_retry`, so its retry prompt gets the guide with no change; ticket 06/07 builder feedback prompts (`FLOOR_FAILURES.md`, `TASK_CHECK_FAILURES.md` routed to the builder) get it from `build_prompt_for_agent` without any wiring.
- `fsm_compose.py` is at 388 lines; ticket 12 or later adding to it must go in a new file.
