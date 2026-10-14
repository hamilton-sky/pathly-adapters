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
