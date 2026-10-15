# Map: build-proof

## Destination

Pathly's headless runs prove a build is done instead of trusting the agent. A new pure
`pathly_orchestrator/proof/` package runs commands, parses and runs ```check blocks, snapshots
the git working tree and scans a diff for weakened tests (the floor guard).

In `team` and `team-build`, these gates run at the transitions out of BUILDING, REVIEWING and
TESTING and into DONE, judging the whole run since a run-wide `proof_base`, so builder fix
rounds inside those states are judged too:

- `floor_gate`, `task_checks` and a narrowed `scope_gate` send the builder back;
- `reviewer_unchanged` parks the run for a human when a reviewer spawn changed files or `HEAD`.

The reviewer gets a Review packet (the frozen task text and the diff) instead of the builder's
`AGENT_DONE` summaries, in a fresh CLI session instead of the builder's resumed one.

In `goal-loop`, every task attempt that reports success is checked after it returns: floor scan,
task-text edit and the task's own check blocks. A failure goes through the existing
`task_retry` path with the real output. The join (`DRAINING->DONE`) then runs `floor_gate` over
the whole run's diff and `task_checks` for any task not yet proven, so a builder fix round after
the drain cannot weaken the bar or skip a task's checks either.

Task text is frozen at claim (`claimed_text`). Only a human can set a task's `floor_allow` list.
DAG task prompts carry their dependencies' results, and retry prompts carry a root-cause guide.
A red base parks the run before any spawn, and goal runs get an iteration budget sized from
their DAG.

**The bar.** `python -m pytest tests/fsm_flows/test_build_proof_acceptance.py -q -p no:cacheprovider`
passes. It drives the real `team-build` and `goal-loop` flows through `supervisor.start_run`,
with scripted fake agents and no model, and shows each of these:

- a builder that skips a test is sent back by the floor gate;
- a task whose check block fails after it reports success is retried with the real check output
  and then fails;
- a builder that edits its own task text or the plan is caught;
- a reviewer that edits a tracked file fails the review stage;
- a red base blocks the run before any agent is spawned;
- a dependent task's prompt carries its dependency's result;
- a retry prompt carries the debugging fragment;
- a clean happy path reaches DONE.

And `python -m pytest tests/ -q -p no:cacheprovider` passes in full, with the Lint command in
`commands.md` green. Ticket 14 runs all of it.

## How to work this

- Plans live in `pathly/features/` (root `CLAUDE.md`, "Feature plans"), so run the scripts with
  `FLOW_DIR=pathly/features FLOW_TICKETS=tasks`.
- See what is ready: `python3 scripts/flow-status.py build-proof`. Take the lowest numbered READY
  ticket.
- Claim: set `Status: claimed` in the ticket and save before starting.
- Resolve: write the result under `## Answer`, set `Status: resolved`, then add one line to
  Decisions so far below.
- See the graph: `python3 scripts/flow-status.py build-proof --mermaid` (coloured by status, drawn
  on demand).
- Commands live in `commands.md` (frozen). Lessons live in `learnings.md` (append only).
- Status lives only in the ticket files. This map never repeats it.
- Design and every interface are in `spec.md` (§ Decisions, § Interfaces). Port from
  `/home/claude/hamilton-sky/feature-flow` (MIT): copy patterns into Pathly modules, never import
  it, and never import this repo's own `scripts/floor-guard.py` from `src/`.
- Hard rules from `CLAUDE.md`:
  - 400-line ratchet (`scripts/check_file_size.py`). `db/queries/comms_tasks.py` is frozen at 418
    lines, so edit its lines in place. `supervisor/orchestrator.py` (399),
    `supervisor/scheduler.py` (393) and `http_server/blueprints/comms/messages_write.py` (400)
    have almost no room, so put new code in new files.
  - The layer rule `db -> runner -> supervisor -> http_server`, with imports kept lazy inside
    routes. `proof/` and `fsm/` sit outside the layers, and `proof/` imports nothing internal.
  - New endpoints go in a new blueprint file.
  - Living docs change in the same ticket as the code.
  - Test basenames are unique across folders. Run `python scripts/gen_test_index.py` after adding
    a test.
  - Bandit (`-ll`): no f-string or `+` SQL building in new code, never `# nosec`, no
    `shell=True`.
- The lint chain has no flake8 or ruff, so a re-export needs no `# noqa`. Do not add `# noqa`,
  `# type: ignore` or `# pragma: no cover` lines: the conductor's floor guard counts them as
  `suppress`. Do not edit `tests/conftest.py`, `pyproject.toml` tool sections or CI files
  (`config`).
- Golden snapshots: when a ticket changes a composed skill or fragment, write
  `compose_skill(<skill>, "claude")` to `tests/snapshots/<skill with / as __>.claude.md` and
  check `tests/install_skills/test_compose.py` passes.
- Tests that `git init` a temp repo must set a git identity in that repo
  (`git config user.email …` and `user.name`, as `tests/telemetry/test_stage_provenance.py`
  does): CI has none. CI runs Ubuntu with Python 3.11, 3.12 and 3.13.
- A test that calls the real `fsm_compose.build_prompt` should set the app setting
  `code_context.backend` to `off`. Otherwise the `auto` backend may start a code-intel tool.
- The test suite may leave a gitignored `.serena/` folder in the repo root (a code-intel test
  starts Serena through `uvx`). It is harmless; do not commit it.

## Decisions so far

- Before 01 (plan) — git can build a tree object from a private copy of the index. Point
  `GIT_INDEX_FILE` at a temp copy of the file `git rev-parse --git-path index` names. Run
  `git add -A` there (it stages adds, changes and removals, and never ignored files), then
  `git write-tree` (prints the tree id; it needs a fully merged index, so when it fails the
  snapshot is `None` and callers fail open).
  The repo's real index and `HEAD` are not touched. docs:
  https://git-scm.com/book/en/v2/Git-Internals-Environment-Variables,
  https://git-scm.com/docs/git-rev-parse, https://git-scm.com/docs/git-add,
  https://git-scm.com/docs/git-write-tree
- Before 01 (plan) — `git diff` takes two tree ids wherever it takes two commits, and
  `--name-status`, `--no-renames` and `--unified=0` behave as on commits. docs:
  https://git-scm.com/docs/git-diff
- Before 01 (plan) — git pathspecs have a long form, `:(<magic words>)<pattern>`, and `exclude`
  is one of the magic words (short form `!` or `^`). A path that matches is dropped. When no
  non-exclude pathspec is given, the exclusion applies to everything, as if no pathspec were
  given. So `git diff <tree-a> <tree-b> -- ':(exclude)pathly/'` diffs every path outside
  `pathly/`; checked here on git 2.43 against two `write-tree` snapshots, with the real index
  left untouched. docs: https://git-scm.com/docs/gitglossary#Documentation/gitglossary.txt-pathspec
- Before 01 (plan) — snapshot objects are unreachable. `git gc` prunes loose unreachable objects
  older than `gc.pruneExpire` (two weeks by default). docs: https://git-scm.com/docs/git-gc
- Before 01 (plan) — headless prompts travel as one argv string (`claude -p '{prompt}'`), and
  Linux caps a single argument at 32 pages (`MAX_ARG_STRLEN`, 128 KiB with 4 KiB pages), so
  anything this feature appends to a prompt (Review packet, check reports, dependency results)
  is clipped. The packet's diff stays under 48 KiB. docs:
  https://man7.org/linux/man-pages/man2/execve.2.html
- Before 01 (plan) — `datetime.fromisoformat` reads any valid ISO 8601 string from Python 3.11
  (before, only what `isoformat()` emits), and the docs show a trailing `Z` parsing to UTC. The
  package requires Python 3.11 or newer (`pyproject.toml`), so event `ts` values (`...Z`) and
  `isoformat()` stamps compare as parsed datetimes. docs:
  https://docs.python.org/3/library/datetime.html#datetime.datetime.fromisoformat
- Before 01 (plan) — `git rev-parse --show-toplevel` prints the top folder of the work tree;
  snapshots fail open when it is not the project root. docs: https://git-scm.com/docs/git-rev-parse
- Before 01 (plan) — `claude --resume <session-id>`, which `core/adapters.yaml` adds to a
  same-adapter stage, restores the session's full conversation history, tool calls and results
  included, and `claude -p --resume <session-id>` sends the new prompt into that conversation. So
  a reviewer that resumes the builder's session has read the builder's transcript. docs:
  https://code.claude.com/docs/en/sessions
- Before 01 (plan) — Black defaults to 88 characters per line unless `--line-length` (or
  `line-length` under `[tool.black]`) changes it, and this repo's `[tool.black]` sets only
  `target-version`, so `black --check` (pinned `black==26.5.1`) allows 88. The `resolve_session(`
  argument line ticket 16 writes is 86 characters, and `black --check` leaves a copy of
  `orchestrator.py` with that edit at three lines and 399 lines in all (checked here). docs:
  https://black.readthedocs.io/en/stable/the_black_code_style/current_style.html#line-length
- Before 01 (plan) — feature-flow sources ported: `feature_flow/floorguard.py` (regexes
  `SKIP`, `FOCUSED`, `SUPPRESS`, `EMPTY_CATCH`, `TRIVIAL`, `THRESHOLD`, `DELETED_TEST`, `CONFIG`,
  pyproject/setup.cfg/package.json/conftest/Makefile content rules, `count_assertions`),
  `feature_flow/proof.py` (`checks_in`, `run_checks`), `feature_flow/conductor.py` (`run_limit`,
  `judge_review`, `run_smoke`), `guides/debug.md`. Local, MIT licensed.
- 01 — `proof/command.py` (`to_argv`, `clip`, `run_command` -> `CommandResult`, never raises) is the one command runner; `command_gate` uses it with unchanged feedback. `proof/checks.py` parses every ```check fence anywhere in task text (feature-flow grammar and messages) and `run_checks(checks, cwd, timeout)` runs all of them, no shell, timeout in seconds.
- 02 — `proof/tree.py` snapshots the working tree into a tree id (private index copy, `git add -A`, `write-tree`) and diffs tree ids (`head`, `changes`, `diff_text`, `blob`, plus `read` for a file's text); every call fails open unless `root` is the git top folder. `proof/floor.py` `scan()` ports feature-flow's patterns and config content rules over two snapshots, outside `pathly/` only, plus `plan-edit` for `protected` prefixes; `parse_allow` raises `ValueError` naming the valid categories.
- 02 (review round 1) — `tree.snapshot` copies the index with `shutil.copy2` (keeps its mtime, so git's racy-clean check still re-reads a same-second edit); `_git` also drops the four `GIT_*_PATHSPECS` variables; `floor` unquotes C-quoted patch header names (`tree.unquote_path`); `FloorReport.error` (default `None`) says what git could not diff or read, from `tree.changes_or_none` / `tree.diff_text_or_none`, and the findings it did make stay real.
- 03 — `claim_task` freezes `text` into `claimed_text` with `COALESCE` (first claim wins, kept across retries and released claims); `floor_allow` is a JSON list whose only writer is `POST /comms/tasks/floor-allow` (403 for a live run token, a tokenless caller counts as human, `refreeze` re-copies the text); `db/queries/task_proof.py` `get_task` returns any live row type, and the `*_since` windows compare parsed times, goal-scoped else `(board, scope)`.
- 04 — `supervisor/spawn_window.observe` wraps `fan_out.run_stage`'s single spawn (role `role_map[state]`) and the feedback spawn (role `target_agent`) and, when the flow has a `floor_gate`, `scope_gate` or `reviewer_unchanged`, appends `SPAWN_WINDOW {role, run_id, state, before, after, head_before, head_after}`; `fsm/gates/_proof.py` has `board_home`, `stage_writes` (the role write table), `windows_since` (parsed times, `since` cut to its second, `ValueError` on a bad one), `explained` (the window must itself have changed the path) and `floor_enabled`.
- 08 — `scope_gate` declares the union of `scope_file`'s backtick paths (now optional) and the `files` of tasks claimed since `build_baseline.started_at` (a directory entry covers its subtree); it exempts only `stage_writes(storage, "builder")`, `exempt_prefixes` and paths a `SPAWN_WINDOW` explains (snapshot only when a window's role may write a path), lists untracked files one by one (`--untracked-files=all`, a baseline `dir/` entry covers its subtree), never lets the scope file cover its own edit, names up to 20 paths, fails open on unreadable tasks/windows/snapshot, and is the last `BUILDING->REVIEWING` gate in `team` and `team-build`.
- 08 (review round 1) — a path already dirty when BUILDING began (`preexisting_dirty`; with `auto_commit` off that is the plan) is judged by content: it counts when its blob differs from the `before` tree of the first `SPAWN_WINDOW` since `started_at`; only a task posted before `started_at` and not stamped `author_role: builder` declares scope (`fsm/gates/_scope_tasks.py`); unreadable windows, snapshot or tree diff still fail a path no role could write (`_proof.any_role_writes`); `_proof.storage_rel` and `task_proof.instant` are public.
- 09 — `fsm/gates/reviewer.py` `reviewer_unchanged` judges only `SPAWN_WINDOW`s of role `reviewer` since the newest `STATE_TRANSITION` into REVIEWING (a `HEAD` move, or a changed path `stage_writes(storage, "reviewer")` forbids), skips windows an earlier `GATE_FAILED.run_ids` named, writes `REVIEWER_CHANGED_FILES.md` (routed to `human`, ranked after `BLOCKED_ON_HUMAN`) and is the last gate of `REVIEWING->TESTING` plus the only gate of the new `REVIEWING->BUILDING` key in `team` and `team-build`; fails open on unreadable windows or diffs.
- 10 — `next_action` stamps `build_baseline.tree`; leaving BUILDING copies `{tree, started_at}` into `review_base` (dropped when the build had no tree); `build_prompt` swaps the history block for `fsm_compose_review.review_packet` (frozen task text, diff outside `pathly/` with 3 lines of context clipped to 48 KiB, `TASK_PROOF`/`FLOOR_CHECKED` notes) for the `reviewer` role; `RUNNER_CONTRACT_BLOCK` forbids spawning a role to resolve a feedback file in any headless stage; `team/review` has its orchestrator paste the packet (and hydrate `context_refs`) for the no-Bash reviewer.
- 11 — `build_task_prompt` adds `## Results of the tasks this one depends on` (`supervisor/task_dependencies.py`; one `###` per direct dependency, its newest `sched-<id>#<n>` `AGENT_DONE` summary from `db/queries/task_results.latest_task_summaries`, 2000/8000 clips, `(no result recorded)`); `fragments/root-cause-debug.md` (not in `composition.yaml`, read through `compose_resources.root_cause_guide()`) is appended in `task_retry.build_retry_context` and in `build_prompt_for_agent` for a `builder` given a `feedback_file`; the old `test_fix_routing` builder-byte-identical test now expects exactly that guide and nothing else.
- 12 — `api.start_run(..., smoke_base=True)` calls `supervisor/base_smoke.check_base` before `_loop`: for a flow whose gates hold a `command_gate` on `build` it runs `verify.smoke` else `verify.build` (neither = skip) in the project root; red, timeout or unrunnable posts a `system`-stamped human escalation (`supervisor/human_escalation.post_human_escalation`, moved out of `orchestrator_stage`), sets `error_kind="base_red"`, parks and broadcasts `RUNNER_PARKED kind base_red` with nothing spawned; `resume_parked_run` re-smokes only after `base_red`; `supervisor/run_budget.refresh` (first line of `_resolve_stage_supervised`) raises a goal run's `max_iterations` to `tasks × goal.task_max_attempts × (MAX_FEEDBACK_ROUNDS + 1)`, never lowers it.
- 13 — `planning/plan` swaps the phase `Verify:` field for a `Check:` field (a ```check block in the supervisor's grammar, read-only, no shell, the project's real commands; required at standard/strict, optional in lite, or one line `Check: none - <why>`); the `task-dag-post` fragment says a task's `text` carries that block verbatim (JSON-escaped `\n` in the curl body), that the supervisor runs it from the text frozen at claim, and that `files` also sets `scope_gate`'s scope; `tests/install_skills/test_planner_check_blocks.py` parses the examples in both with `checks_in`; only the `planning__plan` golden moved (the fragment is goal_id-gated).
- 15 — `fsm/gates/_proof_record.py` holds the run-wide base and the proof records: `next_action` stamps `proof_base {tree, started_at}` the first time the run is in a state with an outgoing `floor_gate` or `task_checks` gate (`tree` is `None` outside git, `started_at` always set); `complete_stage` pops it only on the transition into DONE; `record_task_proof` / `task_proven` write and read `TASK_PROOF` (proven = newest record for the task has its current `claimed_at`, `checks` passed or none, `floor` not failed); `read_proof_base` and `task_proven` fail open. No gate calls any of it yet.
- 05 — `supervisor/task_proof.wrap` (inside `tracker.wrap`, in `drain.drain_frontier`) proves each `sched-<id>#<n>` task that reports success: before/after tree snapshots, `floor.scan` over the attempt's diff (paths declared by overlapping in-flight tasks left out, `floor_allow` from the live row), a `task-edit` finding when `claimed_text` differs from `text`, the task's own check blocks; it writes `TASK_PROOF` (even for a failed attempt) and returns the outcome as `failed` with a `## Floor guard` / `## Task text` / `## Checks` error of at most 4000 characters, which the existing `task_retry` path carries (caps `[:500]`/`[:2000]` raised to `[:4000]`); `build_task_prompt` shows `claimed_text`; fails open on anything it cannot do.
- 06 — `fsm/gates/floor.py` `floor_gate` scans the working tree against the run-wide `proof_base.tree` with `proof.floor.scan` (allow = union of the claimed tasks' `floor_allow`, `task-edit` per task, `plan-edit` unless the builder stage may write the path or a `SPAWN_WINDOW` since the base explains it), writes `FLOOR_FAILURES.md` (→ builder) and appends `FLOOR_CHECKED {warnings}` on every scan; it skips (`GATE_SKIPPED`) when `floor.enabled` is off, there is no base or tree, or the snapshot/tasks/scan fail; it sits after the existing gates (before `scope_gate` / `reviewer_unchanged`, which stay last) on `BUILDING->REVIEWING`, `REVIEWING->TESTING`, `TESTING->RETRO`, `->DONE` in `team`/`team-build` and after the two `command_gate`s of goal-loop's `DRAINING->DONE`; an interactive run (no windows) reads another role's plan file as a `plan-edit`.
- 07 — `fsm/gates/task_checks.py` (`task_checks`) runs the check block of every task completed since `proof_base.started_at` whose newest `TASK_PROOF` does not prove its current claim, from `claimed_text`, with `run_checks`; it records a `TASK_PROOF` (`run_id` `gate:<transition>`, `floor: n/a`) per task run and fails with `TASK_CHECK_FAILURES.md` (one section per failing task, quoting a `ParseError`); it skips on `no_proof_base` / `tasks_unreadable`, and sits after `floor_gate` on `BUILDING->REVIEWING` and `REVIEWING->TESTING` (before `scope_gate` / `reviewer_unchanged`), last on `->DONE` in `team`/`team-build` and last on goal-loop's `DRAINING->DONE`, with `TASK_CHECK_FAILURES: builder` routed.
- 07 (review round 1) — `proof.checks.run_task_checks(task, cwd, timeout)` and `proof.command.clip_to(text, limit)` are the one task-check runner and head-and-tail clip: `task_checks` and `supervisor/task_proof` both import them (their private copies are deleted); `_proof_record.unproven(storage, tasks)` reads the event log once per gate run; a block that cannot be parsed gets its own action line (the builder writes `HUMAN_QUESTIONS.md` and stops, a human re-freezes the text) instead of "fix the code".
- 16 — a reviewer stage never resumes the previous stage's CLI session: `orchestrator_session.resolve_session(..., stage_agent)` returns `session_id=None` when `fsm_compose_tables.agent_role_of(stage_agent)` is in `INDEPENDENT_ROLES` (`{reviewer}`; the `SESSION` event then has `kind: opened`, `independent: true`), `_loop` passes `response.get("agent", "")`, and `build_prompt` and `terminal_identity._spawn_role` use the same helper; `_loop` still stores the reviewer's own session as `open_session`, so TESTING (or the next BUILDING) continues the reviewer's. `fsm_compose_paths.resolve_stage_out_path` still has an inline copy of the mapping.
- 14 — `tests/fsm_flows/test_build_proof_acceptance.py` (11 tests: bar items 1 and 3 and 8 are one test per flow, 2, 4, 5, 6, 7 one each) runs the bar through the real `supervisor.start_run` with `team-build` and `goal-loop`, `fhc` patched to in-process `fsm_ops` and a scripted fake in place of `_run_stage_via_terminal` (`build_proof_acceptance_support.py` = project, fake agent, `drive`; `build_proof_acceptance_runs.py` = the scenarios); items 1 and 2 `keep()` their runs and item 7 reads their prompts through `kept()` (it runs a scenario itself when run alone); a mutation pass (floor, task proof, task-edit, reviewer gate, smoke, dependency block, root-cause guide, fresh reviewer session, `task_checks` each switched off in turn) made the matching test fail. The `CHANGELOG.md` "(build-proof)" entry is under Unreleased, and the living docs were checked against the code: only the `fsm/gates/` row of the split-modules table and the `verify.smoke` sentence in `src/pathly_orchestrator/CLAUDE.md` were stale.
- Follow-ups after 14 (the user chose both on 2026-10-15): 17 reads another role's plan-file write as the builder's only when the run recorded spawn windows (the interactive-run false positive in § Open questions, and the Limits sentence of 06), and 18 names the feedback file, and shows its text, in a feedback spawn's prompt (the last open question). Both are independent of each other and of the rest.

## Open questions

- Headless runs never write `retry_count_by_key` to STATE, so the FSM retry ladder
  (`fsm_compose._retry_ladder_block`) and `escalation_routing` never climb in headless runs. The
  supervisor fails a stage after `MAX_FEEDBACK_ROUNDS` instead. This plan works around it (the
  debug guide is added to every builder feedback prompt) and does not fix it: fixing it changes
  escalation behaviour, which the brief did not ask for.
- The floor-allow route has no Studio control yet (Studio UI is out of scope). Until one exists,
  a human sets an allow list with `curl` from a shell without a run token.
- Lane-parallel goal-loop tasks share one working tree. Sound per-task attribution of an
  undeclared write needs `WorktreeIsolation`, which is still a stub.
- Interactive `/pathly` runs record no `SPAWN_WINDOW`, so `scope_gate` cannot judge a path that was dirty when BUILDING began (an uncommitted plan) there. When ticket 10 stamps `build_baseline.tree`, the gate can diff from it instead of the first window's `before` tree.
- A builder feedback prompt does not name its feedback file. `build_prompt_for_agent` adds the file's name and text (`_retry_ladder_block`) only from `retry_count > 0`, which a headless run never reaches, so the builder spawned for `FLOOR_FAILURES.md`, `TASK_CHECK_FAILURES.md` or `TEST_FAILURES.md` gets the agent text, the storage path and the `## Root-cause debugging` guide, whose first step says "Read every failure above". The acceptance test (`assert_sent_back`) found it: the spawn is made while the file is in `feedback/`, but its prompt never says so. Ticket 11 put the guide there on the expectation that the failure was above it. Left alone here (new behaviour, and it changes every builder feedback prompt).
