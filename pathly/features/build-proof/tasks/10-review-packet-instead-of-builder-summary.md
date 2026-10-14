# Give the reviewer the task and the diff instead of the builder's summary

Type: task
Status: resolved
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

Work started at commit `74c85cf05fe47e841af07d432c207dcdba95d37a`. Test-only commit: `345e54b`
(`test(build-proof): 10 failing test`). At that commit `python -m pytest
tests/fsm_flows/test_review_packet.py -q -p no:cacheprovider` gave `28 failed, 2 passed` (exit 1)
for the right reasons: `KeyError: 'tree'` / `'review_base'` (nothing stamped yet),
`ModuleNotFoundError: No module named 'pathly_orchestrator.fsm_compose_review'`, `assert '## Review
packet' in <the REVIEWING prompt>`, and `AssertionError: never spawn another Pathly role` (the
contract sentence). The 2 passes hold before and after: a project outside git gets no tree, and a
BUILDING prompt keeps the history block. The code commit splits that file into four (see Built),
because one file ran to 547 lines, and adds the missing `complete_stage` step to 8 cases that
called `_packet` straight after `_build`; no case was dropped or loosened (30 cases before and after).

**Built**

- `src/pathly_orchestrator/fsm_compose_review.py` (new, 235 lines): `review_packet(storage_path,
  project_root, board, board_scope, goal_id) -> str`. `## Review packet` with the one-line intro,
  `### The task` (`claimed_text` else `text` of `task_proof.tasks_claimed_since` since
  `review_base.started_at`, 16 KiB at most), `### The diff` (`tree.diff_text_or_none(root,
  review_base.tree, <snapshot now>, exclude=["pathly/"], unified=3)` in a fence one backtick longer
  than any run inside it, head and tail clipped to 48 KiB in all, heading and fences included) and
  `### Supervisor notes` (the latest `TASK_PROOF` per claimed task, the warnings of the latest
  `FLOOR_CHECKED`, both since the build began, else `none recorded`). Without a `review_base` tree,
  without a snapshot now, or on any exception it returns a short "No review packet for this run"
  section that tells the stage orchestrator to run `git diff HEAD` itself. It never raises.
- `src/pathly_orchestrator/fsm_ops.py` (+6): `next_action` adds `"tree": proof.tree.snapshot(...)` to
  the `build_baseline` stamp, left out when the snapshot is `None`.
- `src/pathly_orchestrator/fsm_ops_complete.py` (+9): on a transition out of BUILDING,
  `{tree, started_at}` of the popped `build_baseline` becomes `review_base`; the previous one is
  dropped first, so a build with no tree leaves none.
- `src/pathly_orchestrator/fsm_compose.py` (+11): `build_prompt` uses `review_packet(...)` in place
  of the history block when `agent_role == "reviewer"`; `RUNNER_CONTRACT_BLOCK` has one more
  sentence: in any stage never spawn another Pathly role (planner, architect, po, designer,
  builder) to resolve a feedback file, write the file and stop, the supervisor routes it. No braces.
- `src/pathly_data/core/skills/team/review.md`: a "What the reviewer is given" section (paste the
  packet's `### The task` and `### The diff` verbatim; no packet means `git diff HEAD` run by the
  orchestrator; never pass the builder's report, its `AGENT_DONE` summary or `VERIFY.md`); Phase 1
  and Phase 3 carry `[Review packet: The task and The diff]` instead of `Run: git diff HEAD~1 HEAD`;
  the orchestrator hydrates `context_refs` itself. Snapshot `tests/snapshots/team__review.claude.md`
  regenerated from `compose_skill("team/review", "claude")`. `team/build.md` and its snapshot
  `team__build.claude.md` are not touched (identical to the base commit).
- Living docs: `src/pathly_orchestrator/CLAUDE.md` (a "Review packet" paragraph after the reviewer
  gate, the `fsm_compose_review` entry in the split-module table, and the scope gate's sub-agent
  limit reworded), `src/pathly_data/CLAUDE.md` (the `team/review` contradiction fix).
- Tests: `tests/fsm_flows/test_review_packet.py` (13 cases: prompt, packet, diff, clipping),
  `test_review_base_state.py` (6: `build_baseline.tree`, `review_base`), `test_review_packet_notes.py`
  (9: supervisor notes, the contract sentence, the `team/review` text), `review_packet_support.py`
  (shared fixtures and helpers, not a test), regenerated `tests/INDEX.md` and
  `tests/fsm_flows/INDEX.md`.

**Proof** (each run fresh after the last code edit, in the review-fix round)

- `python -m pytest tests/fsm_flows/test_review_packet.py -q -p no:cacheprovider`: `13 passed in
  15.13s`, exit 0. On a `git init` project through `team-build`'s real `next_action` and
  `complete_stage`, with the builder changing `src/app.py` and writing an `AGENT_DONE` with summary
  `BUILDER-SAYS-ALL-GOOD`: the REVIEWING prompt (from `complete_stage` and from `build_prompt`)
  contains `## Review packet`, the frozen task text and the `src/app.py` diff line, and neither
  `BUILDER-SAYS-ALL-GOOD` nor `## Pipeline History`; the BUILDING prompt still has the history
  block and the summary; a 200 KiB addition to `src/big.py` gives a diff section of at most 48 KiB
  that keeps `value_0` and `value_3999` and drops `value_2000`, with an "omitted" marker. The same
  file also covers the frozen text beating a later edit, only tasks claimed since the build began
  and in this scope, the `pathly/` exclusion, three lines of context, a markdown fence not closing
  the packet's fence, an unreadable diff, an empty diff, and no `review_base`.
  `test_review_base_state.py` and `test_review_packet_notes.py` together: `15 passed in 14.11s`
  (6 and 9 cases by `--collect-only`).
- `python -c "...print('clean' if 'git diff HEAD~1 HEAD' not in t else 'still there')"`: prints
  `clean`, exit 0.
- `python -m pytest tests/install_skills/test_compose.py tests/fsm_flows/test_runner_contract_shared.py
  -q -p no:cacheprovider`: `105 passed in 11.82s`, exit 0 (the `team/build` snapshot is the base
  commit's, the regenerated `team/review` snapshot matches; the contract is still shared and still
  one copy in each prompt path).
- The ```check block: the same three commands, each exit 0, printing `13 passed`, `clean` and
  `105 passed`.
- Lint (the full chain from `commands.md`): exit 0. black `513 files would be left unchanged`; mypy
  `Success: no issues found in 288 source files`; file size `OK: 948 source files checked; 19 known
  over 400 lines, none new, none grown`; mirror reads OK; `All test INDEX.md files up to date.`;
  lint-imports `Contracts: 1 kept, 0 broken.`; bandit no findings; adapters OK; entry points OK.
- Smoke: exit 0. Build (`python -m build --wheel`): `Successfully built
  pathly_adapters-2.24.1-py3-none-any.whl`, exit 0; the wheel lists `fsm_compose_review.py`.
- Test (`python -m pytest tests/ -q -x -p no:cacheprovider`): `2619 passed, 14 skipped in 432.42s
  (0:07:12)`, exit 0 (two fewer than before: the removed `team/build` and `team/review` note cases).

**Decisions**

- `diff_text` already had `unified` (ticket 02 added it with default 0), so `proof/tree.py` is
  untouched. The packet calls `diff_text_or_none` (same text) so that a git failure or a pruned
  snapshot reads "The diff could not be read" instead of looking like an empty diff.
- A build whose baseline has no tree removes `review_base` rather than keeping the previous build's:
  a stale base would show the reviewer a diff of the wrong build.
- The ticket says Phase 1 and Phase 3 "no longer tell the reviewer to run anything", and Phase 3 also
  had the reviewer `GET /comms/artifacts/section` for `context_refs`, which it cannot do without
  Bash. The stage orchestrator now hydrates the refs and pastes their `text` under `## Referenced
  spec`. The run-token instruction line for that call stays in the file (the consistency test needs it).
- Caps the ticket did not name, for the argv limit: the task section is clipped to 16 KiB, floor
  warnings to 20 lines of 300 characters. The diff clip counts bytes, not characters, and cuts at
  line boundaries when it can.
- Events are read from `review_base.started_at` on (cut to its second, as `windows_since` does), so a
  `TASK_PROOF` or `FLOOR_CHECKED` from an earlier build is not shown; a task with no `TASK_PROOF` gets
  no line, and when nothing is left the section says `none recorded`.
- The reviewer role gets the packet section even when it is the "No review packet" one, so it never
  receives the builder's `AGENT_DONE` summaries.
- The contract sentence says "In any stage ... whatever the skill above says", because a planner or
  architect sub-agent has no `SPAWN_WINDOW` of its own in any stage (the reviews of 08 and 09 both
  raised it). The sentence alone stops the fixers in `team/build.md` and `team/review.md` in
  headless runs; the skills are not edited for it (spec.md § Decisions chose the sentence).

**Shortcuts taken**

- `build_prompt_for_agent`'s retry-ladder block (a feedback prompt from retry round 2, e.g. a
  reviewer routed `REVIEW_INCOMPLETE.md`) still lists the `AGENT_DONE` summaries, the builder's
  included. The ticket scopes the change to `build_prompt`. It stops at a reviewer's retry prompts;
  worth closing when ticket 16 touches the reviewer's session, by dropping other roles' summaries
  for the reviewer role.
- The notes read `TASK_PROOF {task_id, checks}` and `FLOOR_CHECKED {warnings}` by the field names in
  spec.md § Interfaces. Nothing writes either event yet (tickets 05 to 07 do), so the tests append
  them by hand. A writer that spells a field differently makes the notes say `none recorded` or a
  raw `checks: <value>` line instead of failing; those tickets' tests should pin the packet.
- The test split uses a shared non-test module `review_packet_support.py` that three test files
  import from (pytest puts `tests/fsm_flows/` on `sys.path`); a conftest would have been config.

**Review fixes**

Round 1, spec review: one finding (scope), accepted as written, and the operator's correction named
the same removal list.

- `src/pathly_data/core/skills/team/build.md` and `tests/snapshots/team__build.claude.md`: restored
  to the base commit `74c85cf` (`git diff 74c85cf` over both is empty), so the "Interactive
  `/pathly` only" blockquote on "Feedback routing after builder" is gone.
- `src/pathly_data/core/skills/team/review.md`: removed the matching blockquote under "Feedback
  routing after reviewer". Kept only what the ticket calls for: the "What the reviewer is given"
  section, the Phase 1 and Phase 3 edits, and the orchestrator hydrating `context_refs`.
  `tests/snapshots/team__review.claude.md` regenerated from `compose_skill("team/review", "claude")`.
- `tests/fsm_flows/test_review_packet_notes.py`: removed the parametrized test that pinned the two
  notes (`team/build` and `team/review`, two cases) and the docstring sentence about them. The file
  has 9 cases now, the three files 28 (13 + 6 + 9) where they had 30; no other case changed.
  `tests/fsm_flows/INDEX.md` regenerated (that file's count 8 to 7).
- Both CLAUDE.md files: dropped the sentences saying the two skills mark their fixer spawns
  "Interactive `/pathly` only" and that the snapshots of both skills pin the text. The Review packet
  paragraph now says the sub-agent fixers in `team/build.md` and `team/review.md` stay for
  interactive `/pathly`, which the ticket itself states. The ticket's own living-doc edits stay.
- Kept: the `RUNNER_CONTRACT_BLOCK` sentence ("In any stage ... whatever the skill above says"). It is
  what the ticket calls for and it covers every stage, so it is the only thing that stops the
  fixers headless.

**For later tickets**

- 05 to 07: the notes need `TASK_PROOF.task_id`, `TASK_PROOF.checks` in `passed|failed|none|error`
  and `FLOOR_CHECKED.warnings` as a list of strings. When they exist, edit the sentence "nothing writes
  them yet" in `src/pathly_orchestrator/CLAUDE.md` (the "Review packet" paragraph).
- 16: this ticket changes only the prompt. A same-adapter REVIEWING stage still resumes the builder's
  session; the packet's "left out" is honest only once ticket 16 opens a fresh one.
- Any ticket that touches `team/review.md` regenerates `tests/snapshots/team__review.claude.md`
  (`team/build.md` has its own, `team__build.claude.md`, unchanged by this ticket).
- `build_baseline.tree` now exists for every BUILDING the FSM server stamps, so the scope gate's open
  question in map.md (interactive runs have no `SPAWN_WINDOW`) can diff from it. Not done here.
- `review_base` is the last BUILDING's base only: after a `REVIEWING->BUILDING` round the packet shows
  that round's changes, not the whole feature. Ticket 14's acceptance run should expect that.

## Review findings (round 1, spec review)

SPEC
- `python -m pytest tests/fsm_flows/test_review_packet.py -q -p no:cacheprovider` passes, with the REVIEWING / BUILDING / 200 KiB coverage: MET. It printed `13 passed in 15.11s`. I read the tests and they cover each listed case:
  - The REVIEWING prompt has `## Review packet`, `FROZEN-TASK-TEXT` and the `src/app.py` diff line, and lacks `BUILDER-SAYS-ALL-GOOD`.
  - The BUILDING prompt keeps `## Pipeline History`.
  - A 200 KiB diff is clipped to at most 48 KiB.
- `team/review.md` no longer asks anyone to run `git diff HEAD~1 HEAD` (the `python -c` check): MET. It printed `clean`.
- `python -m pytest tests/install_skills/test_compose.py tests/fsm_flows/test_runner_contract_shared.py -q -p no:cacheprovider` passes: MET. It printed `105 passed in 11.35s`.
- scope: NOT OK. These two files are outside what the ticket calls for:
  - `src/pathly_data/core/skills/team/build.md` gained an "Interactive `/pathly` only" blockquote.
  - `tests/snapshots/team__build.claude.md` was regenerated to match it.

  The ticket's skill section covers only `team/review.md`, and Done when names one snapshot, `team__review.claude.md`. The ticket says the single `RUNNER_CONTRACT_BLOCK` sentence is what stops the fixers in `team/build.md` and `team/review.md` from running headless and leaves them for interactive use. spec.md § Decisions chose that sentence alone (option A). It did not choose editing the skills. Nothing in the ticket's Not-in-this-ticket list rules the edit out, but nothing calls for it either. The same unrequested note also went into `team/review.md` under "Feedback routing after reviewer", outside the Phase 1 / Phase 3 edits the ticket specifies. It is in a file the ticket does name, so it is borderline.

  The extra edits are carried into other files:
  - A parametrized test in `tests/fsm_flows/test_review_packet_notes.py` pins the notes.
  - Both CLAUDE.md files describe them.

  Fix: drop the `team/build.md` hunk and the `team__build` snapshot hunk. Also drop the matching test case and doc sentences, and probably the review.md routing note. Or have the ticket amended to call for them.
- Files I checked and treated as in scope: `fsm_compose_review.py`, `fsm_ops.py`, `fsm_ops_complete.py`, `fsm_compose.py`, `team/review.md` Phase 1 / Phase 3, `team__review.claude.md`, the three new test files and the test indexes, the two CLAUDE.md files, and the `learnings.md` / `map.md` lines, which match earlier tickets' pattern.
- Range: I reviewed `74c85cf..2d0decb`. `2d0decb` is HEAD and also the newest commit touching the ticket, so no later commits were excluded. The working tree was clean.
- test first: OK. Commit `345e54b` added `tests/fsm_flows/test_review_packet.py` before the production commit. Without the change, `fsm_compose_review` does not exist and the REVIEWING prompt carries no `## Review packet`, so the file's tests would fail.

Behaviours checked against the ticket text, with no deviation from the ticket: `unified` was already on `diff_text` at base, and `next_action` adds `tree` only when git can snapshot. `complete_stage` rebuilds `review_base` on every transition out of BUILDING. A build with no tree leaves no `review_base`, a reasonable reading of "overwriting the previous one". The `RUNNER_CONTRACT_BLOCK` sentence contains no braces.

REVIEW: FAIL
