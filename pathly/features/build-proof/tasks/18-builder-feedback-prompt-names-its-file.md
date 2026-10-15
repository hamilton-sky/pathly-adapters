# Name the feedback file, and show its text, in a feedback spawn's prompt

Type: task
Status: resolved
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

**Built**

- `src/pathly_orchestrator/fsm_compose_feedback.py` (new, 53 lines): `read_feedback(storage_path, feedback_file)` (the file's text, stripped, clipped to 4000 characters, `""` when it cannot be read or is only whitespace) and `feedback_block(storage_path, feedback_file)` (the `## Feedback to resolve` section).
- `src/pathly_orchestrator/fsm_compose.py` (386 -> 384 lines): `_retry_ladder_block` calls `read_feedback` in place of its inline read; `build_prompt_for_agent` adds `feedback_block` in an `elif` after the ladder, when `feedback_file` is given and `agent_name` is not in `_FIX_MODE_ARTIFACT`, so it sits right after `## Current task` and before Fix mode and the root-cause guide. The three callers are untouched.
- Tests: new `tests/fsm_flows/test_feedback_prompt_names_file.py` (23 tests: the seven listed cases, plus an empty file, a file that is not UTF-8, a text without backticks, a run of four backticks, and `read_feedback` / `feedback_block` on their own); updated `tests/fsm_flows/test_retry_ladder.py`, `tests/fsm_flows/test_fix_routing.py` and `assert_sent_back` in `tests/fsm_flows/test_build_proof_acceptance.py`; regenerated `tests/INDEX.md` and `tests/fsm_flows/INDEX.md`. These went in the test-only commit `58b71df`.
- Docs: the "Retry ladder" section and the `fsm_compose` row of the split-modules table in `src/pathly_orchestrator/CLAUDE.md`; the build-proof "Known limits" paragraph in `CHANGELOG.md`.

**Proof** (each run fresh, after the last edit; venv on PATH)

- `python -m pytest tests/fsm_flows/test_feedback_prompt_names_file.py -q -p no:cacheprovider`: `23 passed in 0.59s`, exit 0. At the test-only commit it failed: 14 of the 23 (the rest pin behaviour that did not change).
- `python -m pytest tests/fsm_flows tests/dag_goals tests/runner_supervisor -q -p no:cacheprovider`: `1212 passed, 9 skipped in 258.47s`, exit 0 (the updated tests and the acceptance test included; none of the 9 skips is in a file this ticket changed).
- `python scripts/check_file_size.py`: `OK: 1009 source files checked; 19 known over 400 lines, none new, none grown.`, exit 0. `python scripts/gen_test_index.py --check`: `All test INDEX.md files up to date.`, exit 0.
- The `CHANGELOG.md` one-liner printed `clean`, exit 0.
- The full Test command `python -m pytest tests/ -q -x -p no:cacheprovider`: `2947 passed, 14 skipped in 558.03s`, exit 0. The Lint chain: `black --check src/ tests/` (568 files unchanged), `mypy` (no issues in 313 files), `check_no_mirror_reads`, `lint-imports` (1 kept, 0 broken), `bandit -q -r src/ -ll -x src/pathly_data/` (exit 0), `check_adapters`, `check_entry_points` all exit 0. Build `python -m build --wheel`: built `pathly_adapters-2.24.1-py3-none-any.whl`, exit 0.
- At the test-only commit `assert_sent_back` failed on `'## Feedback to resolve' in spawn.instructions` in both acceptance tests that use it; it passes now.

**Decisions**

- The block goes in an `elif` after the ladder, not under `retry_count == 0`: a retry count that is not above zero (never produced; a negative one would be a bug) gets the block, not nothing.
- `read_feedback` catches `UnicodeError` as well as `OSError`. The old inline read caught only `OSError`, so a feedback file that was not UTF-8 raised inside `_retry_ladder_block` (the callers catch it and the spawn then has no prompt). "Cannot be read" covers it, and the block says so.
- An empty or whitespace-only file gets the "could not be read (the file is missing, unreadable or empty)" block, since showing an empty fence says nothing.
- Wording of the block: "`<path>` is what the gate or reviewer wrote when this stage was sent back. Fix the cause it describes, not the file." The path is `storage_path.as_posix().rstrip("/") + "/feedback/" + file`, the same expression the Fix mode block uses.
- The ladder keeps its own fixed three-backtick fence (the ticket changes only its read); only the new block uses the longer-fence rule.
- `test_build_prompt_for_agent_builder_path_unchanged` was renamed to `..._gains_only_the_block_and_the_guide` because "unchanged" is no longer true; it now asserts `with_feedback == without_feedback + feedback_block(...) + "\n" + guide + "\n"`, one block, the text once, no Fix mode. I added assertions to the other round-1 tests (retry ladder: the block is there once, the text once; round 2: no block) and removed none.
- The `fsm_compose` row of the split-modules table said `(298)`; it is 384 now, so I wrote the real number while adding `fsm_compose_feedback` to it. I also changed the guide paragraph's last sentence ("every other role is byte-identical to before") because a reviewer or tester given a feedback file now gets the block.

**Shortcuts taken**

- The clip is a plain cut at 4000 characters with no marker, as the ladder's was. A feedback file longer than that shows its head only, and the prompt does not say it was cut. Worth a marker if a gate's report is ever found cut mid-section (`task_checks` already clips its own sections to 4000).
- `feedback_block` does not tell the agent whether to delete the file; for a builder the gate that wrote it rewrites or removes it when it re-runs, and the block says nothing about it either way.

**For later tickets**

- No open ticket depends on this. The first open question in map.md is the one left: a headless run still never writes `retry_count_by_key`, so the ladder (with its `AGENT_DONE` history block) and `escalation_routing` never climb; the new block covers what the prompt shows, not the escalation.
- The last item of map.md § Open questions (a builder feedback prompt does not name its feedback file) is resolved by this ticket; I left the map's text as it is.
- A reviewer's or tester's round-1 feedback prompt now holds the file's text, so a test that pins "the reviewer's prompt has no X" for a spawn with a feedback file should expect the block.
