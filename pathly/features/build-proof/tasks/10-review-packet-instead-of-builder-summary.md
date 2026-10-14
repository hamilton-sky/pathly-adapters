# Give the reviewer the task and the diff instead of the builder's summary

Type: task
Status: open
Blocked by: 02, 03
Test first: yes

Today the REVIEWING prompt carries the pipeline history block (the builder's `AGENT_DONE`
summaries, from `runner.build_pipeline_history_block`). `team/review.md` tells a reviewer
sub-agent to `Run: git diff HEAD~1 HEAD`, but the reviewer has no Bash
(`src/pathly_data/adapters/claude/_meta/reviewer.yaml`, `core/agents/quality/reviewer.md`
"Do not run Bash").

**A base for the diff.** In `fsm_ops.next_action`, add `"tree": proof.tree.snapshot(project_root)`
to the existing `build_baseline` stamp (left out when the snapshot is `None`). In
`fsm_ops_complete`, where `build_baseline` is popped on a transition, a transition out of
BUILDING first copies `{"tree", "started_at"}` into `review_base`, overwriting the previous one.

**The packet.** New `src/pathly_orchestrator/fsm_compose_review.py::review_packet(storage_path,
project_root, board, board_scope, goal_id) -> str` returns a `## Review packet` section:

- one line: judge this diff against the task; the builder's own account is deliberately left
  out;
- `### The task`: the `claimed_text` (else `text`) of the tasks claimed since
  `review_base.started_at` (`task_proof.tasks_claimed_since`);
- `### The diff`: `proof.tree.diff_text(root, review_base.tree, <snapshot now>,
  exclude=["pathly/"])`. With no other path given, git applies the `:(exclude)pathly/` pathspec
  to every path, so the diff is everything outside `pathly/` (map.md § Decisions so far, git
  pathspecs). Add an optional `unified` argument to `diff_text` (default 0) and pass 3 here.
  Clip it with head and tail to 48 KiB in all (map.md § Decisions so far, `MAX_ARG_STRLEN`);
- `### Supervisor notes`: for each task, its latest `TASK_PROOF` event (checks passed, failed or
  "no check block: review its acceptance by reading the code"), and the warnings of the latest
  `FLOOR_CHECKED` event. Write "none recorded" when there are none.

With no `review_base` (an interactive run, or git missing) it returns a short section saying so,
and the skill's interactive branch below applies.

In `fsm_compose.build_prompt`, when `agent_role == "reviewer"`, use `review_packet(...)` in place
of `history`. Every other role keeps the history block.

**The runner contract.** Add one sentence to `fsm_compose.RUNNER_CONTRACT_BLOCK` (keep it free of
`{` and `}`; `tests/fsm_flows/test_runner_contract_shared.py` checks that): headless, do not spawn
another Pathly role to resolve a feedback file (planner, architect, po, designer, builder);
write the file and stop, and the supervisor routes it. That one line stops the sub-agent fixers
in `team/build.md` and `team/review.md` from running in headless runs, and leaves them for
interactive `/pathly`.

**The skill.** In `src/pathly_data/core/skills/team/review.md`, Phase 1 and Phase 3 no longer
tell the reviewer to run anything. The stage orchestrator pastes the Review packet's
`### The task` and `### The diff` sections verbatim into the reviewer's prompt. When there is no
packet (interactive), the orchestrator runs `git diff HEAD` itself (it has Bash) and pastes the
output. Never pass the builder's report or `VERIFY.md`. Then write
`compose_skill("team/review", "claude")` to `tests/snapshots/team__review.claude.md`.

Living docs: the Review packet and the reviewer's view in `src/pathly_orchestrator/CLAUDE.md`, and
the `team/review` contradiction fix in `src/pathly_data/CLAUDE.md`.

## Not in this ticket

- The gate that fails a reviewer who changed files: ticket 09.
- The reviewer's CLI session: a same-adapter REVIEWING stage resumes the builder's session, and
  so its transcript, until ticket 16 opens a fresh one. This ticket changes only the prompt.
- Filtering builder posts out of the reviewer's board context: rejected (spec.md § Decisions).
- `development/review.md` (interactive skill, run by the user's own session with Bash):
  unchanged.

## Done when

- `python -m pytest tests/fsm_flows/test_review_packet.py -q -p no:cacheprovider` passes. On a
  `team-build` feature in a `git init` project, after a BUILDING stage where the builder changed
  `src/app.py` and wrote an `AGENT_DONE` with summary `BUILDER-SAYS-ALL-GOOD`, it covers:
  - `build_prompt` for REVIEWING contains `## Review packet`, the task's frozen text and a line
    from the `src/app.py` diff, and not `BUILDER-SAYS-ALL-GOOD`;
  - `build_prompt` for BUILDING still contains the history block;
  - a 200 KiB diff is clipped to at most 48 KiB in the packet.
- `team/review.md` no longer asks anyone to run `git diff HEAD~1 HEAD`:
  `python -c "import pathlib;t=pathlib.Path('src/pathly_data/core/skills/team/review.md').read_text(encoding='utf-8');print('clean' if 'git diff HEAD~1 HEAD' not in t else 'still there')"`
  prints `clean`.
- `python -m pytest tests/install_skills/test_compose.py tests/fsm_flows/test_runner_contract_shared.py -q -p no:cacheprovider`
  passes (regenerated snapshot, contract still shared).

```check
# The conductor runs this block before review.
$ python -m pytest tests/fsm_flows/test_review_packet.py -q -p no:cacheprovider
exit 0
prints passed
$ python -c "import pathlib;t=pathlib.Path('src/pathly_data/core/skills/team/review.md').read_text(encoding='utf-8');print('clean' if 'git diff HEAD~1 HEAD' not in t else 'still there')"
exit 0
prints clean
$ python -m pytest tests/install_skills/test_compose.py tests/fsm_flows/test_runner_contract_shared.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- spec.md § Decisions ("What 'without the builder's summary' removes", "The `team/build.md` and
  `team/review.md` sub-agent fixers"), § Interfaces (STATE keys)
- map.md § Decisions so far (git pathspecs, `MAX_ARG_STRLEN`)
- `src/pathly_orchestrator/fsm_compose.py::build_prompt` (the `history =` line),
  `RUNNER_CONTRACT_BLOCK`
- `src/pathly_orchestrator/fsm_ops.py::next_action`, `fsm_ops_complete.py` (the
  `prior_state.pop("build_baseline", None)` line)
- `src/pathly_data/core/skills/team/review.md` (Phase 1, Phase 3)

## Answer
