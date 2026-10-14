# Narrow scope_gate to what a stage may write and wire it into the team flows

Type: task
Status: resolved
Blocked by: 03, 04
Test first: yes

`fsm/gates/scope.py` exempts every path under `pathly/features/` and `pathly/plans/`, so a
builder can rewrite its own plan. No packaged flow uses the gate. Change it as follows.

- **Declared scope.** The union of:
  - the backtick paths in `scope_file`, when the gate names one and the file exists
    (`scope_file` becomes optional: `gate.get("scope_file")`);
  - the `files` of the tasks claimed since `build_baseline.started_at`
    (`task_proof.tasks_claimed_since(board, feature_scope, goal_id, …)`).

  An entry that names a directory covers everything under it, with or without a trailing `/`
  (`path.startswith(entry.rstrip("/") + "/")`), as `fragments/task-dag-post.md` promises for
  `files`. An empty union still skips with `no_declared_scope`, as today.
- **Exempt.** `.tsbuildinfo` and the flow's `scope_gate.exempt_prefixes` stay exempt. So does a
  path for which `_proof.stage_writes(storage, "builder")` is true, and a path that
  `_proof.explained` attributes to a `SPAWN_WINDOW` since `build_baseline.started_at` (take the
  now-snapshot only when a path needs it). The blanket `pathly/features/` and `pathly/plans/`
  prefixes go.
- **Failure text.** It names the out-of-scope paths (at most 20, then a count), not only the
  scope file.

Flows: add `{type: scope_gate, scope_file: IMPLEMENTATION_PLAN.md, on_fail:
SCOPE_VIOLATION.md}` as the last gate of `BUILDING->REVIEWING` in `team.flow.yaml` and
`team-build.flow.yaml` (spec.md § Migration and compatibility). Both already route `SCOPE_VIOLATION` to `builder`. Update the
`scope_gate` line in `fsm_compose_responses._exit_requirement` to name the claimed tasks' `files`
as part of the scope.

Rewrite the three plan-file exemption tests in `tests/fsm_flows/test_gates.py`
(`test_scope_gate_plan_files_*`) to the new rule:

- a builder edit to a plan file in its own storage now fails the gate;
- a builder write to `feedback/` or `VERIFY.md` passes;
- an undeclared codebase file still fails.

This change of expectation is the point of the ticket.

Living docs: the `scope_gate` description in `src/pathly_orchestrator/CLAUDE.md` (what is declared,
what is exempt, wired into both team flows).

## Not in this ticket

- `goal-loop`: the per-task proof and the join `floor_gate` (`plan-edit`) cover plan edits
  there (tickets 05 and 06). `scope_gate` is not added to it; the brief wires it into the team
  flows only.
- Blocking writes before they happen: the gate still judges after the stage.

## Done when

- `python -m pytest tests/fsm_flows/test_scope_gate_narrowed.py -q -p no:cacheprovider` passes.
  In a `git init` project under `tmp_path`, it covers:
  - a change inside a claimed task's `files` passes;
  - a change outside it fails, naming the path;
  - an edit to `pathly/features/<f>/USER_STORIES.md` by the builder fails;
  - the same edit explained by a planner `SPAWN_WINDOW` passes;
  - `feedback/IMPL_QUESTIONS.md` and `VERIFY.md` pass;
  - a declared `src/pkg` covers `src/pkg/a.py`;
  - with no `scope_file` and no task `files` the gate skips.
- `python -m pytest tests/fsm_flows/test_gates.py -q -p no:cacheprovider` passes with the
  rewritten exemption tests.
- `python -m pytest tests/fsm_flows -q -p no:cacheprovider` passes.

```check
# The conductor runs this block before review.
$ python -m pytest tests/fsm_flows/test_scope_gate_narrowed.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/fsm_flows/test_gates.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/fsm_flows -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- spec.md § Stories ("Scope"), § Migration and compatibility
- `src/pathly_orchestrator/fsm/gates/scope.py` (`_declared_paths`, `_git_dirty`, `_scope_clean`,
  `check_scope_gate`)
- `tests/fsm_flows/test_gates.py` (the `# ── plan-file exemption tests` section)

## Answer

Work started at commit `7639838573d67ac9eff6aeb31f20046349a12eba`. Two test-only commits, both
`test(build-proof): 08 failing test`: `fc72758` (the build) and `a389c67` (review round 1).

- At `fc72758` the three test files gave `24 failed, 51 passed`, every failure an assertion on
  behaviour: 21 of the 22 new cases (the old gate ignored task `files`; the blanket
  `pathly/features/` exemption let a `USER_STORIES.md` edit and a self-widening scope file
  through; the failure text named only the scope file; the packaged flows' last
  `BUILDING->REVIEWING` gate was `command_gate`), the builder plan-edit case and the codebase
  case's text in `test_gates.py`, and `test_spawn_window.py`'s `wants_windows(team-build)`.
- At `a389c67` (checked again in a throwaway worktree of that commit) the review round's three
  test files gave `9 failed, 35 passed`. All nine are in the new
  `test_scope_gate_dirty_baseline.py` and all read `_failed(None)`: the round-1 gate passed a
  builder edit to an uncommitted plan (six cases, finding 1), a task posted after the build
  began or by a builder (two cases, finding 3), and an undeclared code file when the windows
  could not be read (finding 4). The two new cases that passed (an uncommitted plan nobody
  touched; a planner window's edit) must pass either way.

**Built**

- `src/pathly_orchestrator/fsm/gates/scope.py` (172 → 368 lines). `check_scope_gate` reads
  `gate.get("scope_file")` (optional) and declares the union of its backtick paths and the
  claimed tasks' `files` (`_scope_tasks.claimed_files`). `_covered` makes an entry cover itself
  and everything under it, with or without a trailing `/`. `_exemption` is the predicate for a
  declared or exempt path: `_proof.stage_writes(storage, "builder")` (feedback, `VERIFY.md`,
  exports, `*.tsbuildinfo`), `scope_gate.exempt_prefixes` and the declared paths, never the
  scope file's own edit. `_out_of_scope` takes the changed paths that were clean at the
  baseline (`git diff --name-only HEAD` plus every untracked file, `--untracked-files=all`) and
  hands them, with `preexisting_dirty`, to `_unexplained`. That reads the `SPAWN_WINDOW`s since
  `started_at` once. A preexisting path counts when the tree diff from the first window's
  `before` tree to a now-snapshot shows it changed (deletions too). Then it drops what
  `_proof.explained` attributes to a window, looking up blobs only for a path some window's role
  may write. When the windows or the snapshot cannot be read, `_sure_or_skip` fails on the
  paths no window could explain, else skips; a failed tree diff leaves the preexisting paths
  unjudged and skips (`git_diff_failed`) only when nothing else failed. `_failure_text` lists at most
  20 paths, then `- ... and N more`. `_scope_clean` keeps its signature (scope file only). The
  blanket `pathly/features/` and `pathly/plans/` exemption is gone.
- `src/pathly_orchestrator/fsm/gates/_scope_tasks.py` (new, 58 lines): `claimed_files` and
  `_task_files`. A task claimed since `started_at` declares its `files` only when its
  server-stamped `ts` is at or before `started_at` and its `author_role` is not `builder`.
- `src/pathly_orchestrator/fsm/gates/_proof.py`: `_storage_rel` is now public `storage_rel`
  (its two internal callers updated), and new `any_role_writes(storage)`, true for a path some
  role's window could explain.
- `src/pathly_orchestrator/db/queries/task_proof.py`: `_instant` is now public `instant` (its
  two internal callers and `_proof.windows_since` updated).
- `src/pathly_data/core/flows/team.flow.yaml`, `team-build.flow.yaml`: `{type: scope_gate,
  scope_file: IMPLEMENTATION_PLAN.md, on_fail: SCOPE_VIOLATION.md}` as the last
  `BUILDING->REVIEWING` gate, with a comment. Both already route `SCOPE_VIOLATION: builder`.
- `src/pathly_orchestrator/fsm_compose_responses.py::_exit_requirement`: the `scope_gate` line
  names the scope file's paths, the `files` of the planned tasks claimed ("a task you post
  yourself declares nothing"), the feedback files and `VERIFY.md`, and says any other change,
  a plan file included, fails the gate.
- `src/pathly_orchestrator/runner/provenance.py`: the `_is_own_storage` docstring no longer
  says the scope gate exempts `pathly/features/` and `pathly/plans/`.
- `src/pathly_orchestrator/CLAUDE.md`: the `scope_gate` row of the gate table; the "Scope gate"
  paragraph (declared scope and which tasks count, changed paths, judging a baseline path by
  content, exempt, skips and the partial fail-open, wiring) and a "Limits of the scope gate"
  paragraph; the spawn-window and provenance paragraphs no longer describe the old gate.
- Tests: `tests/fsm_flows/test_scope_gate_narrowed.py` (new, 22 cases; its tasks are now posted
  before the baseline, as the planner posts them in PLANNING); `test_scope_gate_dirty_baseline.py`
  (new, 11 cases); the three `test_scope_gate_plan_files_*` tests in
  `tests/fsm_flows/test_gates.py` rewritten; `test_scope_clean_hardcoded_defaults_still_exempt`
  in `tests/telemetry/test_observability.py` now also asserts a `pathly/plans/` plan file fails
  (docstring fixed); `tests/runner_supervisor/test_spawn_window.py`'s packaged-`team-build`
  assertion flipped to `True`; regenerated `tests/INDEX.md`, `tests/fsm_flows/INDEX.md`.

**Proof** (each run fresh after the last code edit, dev venv first on PATH)

- `python -m pytest tests/fsm_flows/test_scope_gate_narrowed.py -q -p no:cacheprovider`:
  `22 passed in 8.01s`, exit 0. In a `git init` repo under `tmp_path`, with `build_baseline`
  written through `eventlog.write_state` and real tasks posted and claimed in the test DB:
  - a change to `src/app.py` inside a claimed task's `files` passes, no `SCOPE_VIOLATION.md`;
  - a change to `src/other.py` outside it fails; the file names `src/other.py`, not
    `src/app.py`, and one `GATE_FAILED` has `gate == "scope_gate"`;
  - a builder edit to `pathly/features/demo/USER_STORIES.md` fails, naming it;
  - the same edit made inside a planner `SPAWN_WINDOW` (real `tree.snapshot` before and after)
    passes; a builder edit after that window fails;
  - `feedback/IMPL_QUESTIONS.md` and `VERIFY.md` pass;
  - a declared `src/pkg` and `src/pkg/` both cover `src/pkg/a.py` and `src/pkg/sub/b.py`;
    `src/pkg` does not cover `src/pkgextra.py`;
  - no `scope_file` and a claimed task with no `files`: the gate passes with exactly one
    `GATE_SKIPPED` `no_declared_scope`;
  - also the union of both sources, a task claimed before `started_at`, goal scoping, files in
    a new untracked folder, a preexisting `scratch/` entry, the self-widening scope file, the
    exempt prefix and `.tsbuildinfo`, plan-only edits with unreadable windows
    (`spawn_windows_unreadable`), 20 named paths then `5 more`, the packaged `team` and
    `team-build` wiring and exit requirement, and `goal-loop` without the gate.
- `python -m pytest tests/fsm_flows/test_gates.py -q -p no:cacheprovider`: `31 passed in
  5.54s`, exit 0, with the rewritten tests: a builder edit to `CONVERSATION_PROMPTS.md` /
  `PROGRESS.md` in its storage fails and the text names both (not `src/app.py`);
  `feedback/IMPL_QUESTIONS.md` and `VERIFY.md` pass; `src/out_of_scope.py` still fails and is
  named.
- `python -m pytest tests/fsm_flows -q -p no:cacheprovider`: `529 passed, 9 skipped in 89.17s`,
  exit 0 (the 9 skips are existing ones, none in the files this ticket touched). It includes
  `test_scope_gate_dirty_baseline.py`, 11 passed: with the plan uncommitted (baseline
  `["pathly/"]`, as `git status` prints it) a builder window's edit to `USER_STORIES.md` fails
  naming only it; a builder widening the uncommitted `IMPLEMENTATION_PLAN.md` with `` `src/` ``
  fails naming it; an untouched uncommitted plan passes with no skip; a planner window's edit
  passes and a builder edit after it fails; an edit after the first window, outside any
  window, fails; a builder deleting the untracked `USER_STORIES.md` fails; a committed plan
  modified before the build (baseline `[USER_STORIES.md]`) passes until a builder window
  changes it again; a task posted after `started_at`, or one stamped `author_role: builder`,
  declares nothing; with `windows_since` raising, an undeclared `src/other.py` fails, named
  alone, with no `GATE_SKIPPED`.
- The check block: the same three commands, each exit 0 and printing `passed`.
- Test (`python -m pytest tests/ -q -x -p no:cacheprovider`): `2571 passed, 14 skipped in
  435.63s`, exit 0.
- Lint (the full chain in `commands.md`): exit 0. black `506 files would be left unchanged`;
  mypy `Success: no issues found in 286 source files`; file size `946 source files checked; 19
  known over 400 lines, none new, none grown`; `check_no_mirror_reads: OK`; `All test INDEX.md
  files up to date.`; lint-imports `Contracts: 1 kept, 0 broken.`; bandit exit 0 with no
  issues; `Adapter consistency OK`; `Entry points OK: 16 checked`.
- Smoke: exit 0 (`946 source files checked`, the five imports load). Build
  (`python -m build --wheel`): `Successfully built pathly_adapters-2.24.1-py3-none-any.whl`,
  exit 0.

**Decisions**

- A path dirty at the baseline is judged by content. `fsm_ops` stamps `preexisting_dirty`
  from `git status` when BUILDING begins, and with `pathly.auto_commit` off the plan is
  always in it (often as one collapsed `pathly/` line). So subtracting those paths, as round 1
  did, let a builder rewrite its own plan. The base is the `before` tree of the first
  `SPAWN_WINDOW` since `started_at`: the supervisor takes it just before the first spawn of
  this BUILDING, so it is the build's starting tree. A single diff from it to a now-snapshot
  shows every preexisting path changed since, inside or outside a window, deletions included
  (`git status` does not list a deleted untracked file). The paths are then judged like any
  other: declared, exempt, or explained by a window. A tree stamped in `build_baseline` would
  do the same job; ticket 10 adds `build_baseline.tree` and owns that stamp, so I did not add
  it here (its test-first commit would pass early).
- With no window (an interactive `/pathly` run) a preexisting path is not judged. Nothing
  records the build's starting tree there, and failing every dirty path would wedge any run
  on a dirty repo.
- Only a task posted before `started_at` (its server-stamped `ts`, which an agent cannot set)
  and not stamped `author_role: builder` declares scope. The time rule stops a builder posting
  and claiming a task in the same BUILDING; the author rule stops one posting a task for a
  later BUILDING (in `team-build` every task gets its own BUILDING). The planner posts tasks in
  PLANNING and the goal decomposer before the run, so both count. A mid-build widening goes
  through the plan: the builder writes `IMPL_QUESTIONS.md`, the planner adds the paths to
  `IMPLEMENTATION_PLAN.md`, and its window explains that edit.
- When the windows cannot be read, the gate still fails on the changed paths no role may write
  (`_proof.any_role_writes` is false: in practice a file outside `pathly/`) and skips only when
  none are left, since the rest (plan files, preexisting paths) cannot be judged. A failed
  snapshot follows the same rule with the roles of the recorded windows. A failed tree diff
  leaves only the preexisting paths unjudged.
- `_scope_tasks.py` holds the task half of the declared scope because the review fixes took
  `scope.py` to 410 lines; moving the two functions this ticket added keeps it at 368 and
  leaves the older functions where they were.
- `task_proof._instant` became public `instant` because the gate now parses the tasks' `ts`
  with it. Reaching into a private helper is what finding 7 objected to, and a second parser
  would duplicate it.
- Kept from round 1: untracked files are listed one by one (`--untracked-files=all`), and a
  `dir/` baseline entry covers the files under it; the scope file never covers its own edit;
  `tasks_unreadable`, `no_build_baseline`, `no_declared_scope`, `git_diff_failed` (git status)
  and `GATE_DEGRADED` fail open; `_scope_clean` stays for its re-exports and
  `tests/telemetry/test_observability.py`; `_task_files` parses `files` itself
  (`supervisor/lane_partition._declared_files` does the same, but `fsm/gates` may not import
  `supervisor`); goal runs read goal-scoped tasks, as `require_tasks_done` does.

**Shortcuts taken**

- An interactive run records no `SPAWN_WINDOW`, so there a path dirty when BUILDING began (an
  uncommitted plan) is not judged. Worth upgrading when ticket 10 stamps
  `build_baseline.tree`: diff from that tree instead of the first window's, and the gate covers
  interactive runs too. Recorded in map.md's Open questions.
- A builder that drops its run token posts tasks stamped `none`, like a human, so it can still
  post a task whose `files` count in a later BUILDING. This is the `force_past_gate` limit; a
  UI token (RRP-2b) would close it.
- A planner routed `IMPL_QUESTIONS.md` inside BUILDING runs with a token minted for `builder`
  (`terminal_identity._spawn_role` reads the state's `agent_map`), so a task it posts then
  never declares scope. Its window-explained edit to `IMPLEMENTATION_PLAN.md` is the way to
  widen the scope. Worth upgrading if planners start posting tasks mid-build: mint the
  feedback spawn's token with its `target_agent`.
- A task claimed in an earlier BUILDING does not declare scope after a `REVIEWING->BUILDING`
  back-edge (the window starts at the re-stamped `started_at`). Its files then stay in scope
  only when the plan names them, as the plan template's `**File:**` lines do; otherwise a fix
  round that changes them again fails the gate. That was already so when `auto_commit`
  committed them at `BUILDING->REVIEWING`; round 1 hid it for uncommitted files by exempting
  every preexisting path, which is what finding 1 closed.
- `git diff --name-only HEAD` (unchanged) lists only the new name of a staged rename and fails
  in a repo with no commits (the gate then skips). Paths git quotes (special characters) come
  quoted from `git status` and unquoted from the tree diff, so such a preexisting path is not
  matched. Left as they were.

**Review fixes** (round 1, quality review)

1. major, an uncommitted plan was exempt as preexisting. Fixed as the reviewer proposed: a
   preexisting path now counts when its content differs from the first window's `before` tree
   since `started_at`, then goes through the same exemptions and window explanations as any
   other. New `test_scope_gate_dirty_baseline.py` takes the baseline from real `git status`
   output with the plan untracked (`["pathly/"]`) and covers an edit, a widened scope file, a
   deletion, an edit outside a window, a planner edit, a builder edit after it, and the
   ` M <file>` case.
2. major, the doc overclaimed. With 1 fixed, the claims hold in every headless run, and the
   "Scope gate" paragraph now says so ("in a headless run ... committed or not") and explains
   why the plan is usually in the baseline. A new "Limits of the scope gate" paragraph names
   what is still not covered: interactive runs, tokenless task posts, and the in-process
   sub-agent of finding 6. The interactive gap is also under map.md's Open questions.
3. minor, a builder could post a task to widen its scope. Fixed with both of the reviewer's
   rules: a task declares scope only when posted at or before `started_at` and not stamped
   `author_role: builder` (`_scope_tasks.claimed_files`). Two new tests. The exit requirement
   tells the builder a task it posts declares nothing.
4. minor, unreadable windows skipped the whole gate. Fixed: the gate fails on the paths no
   role's window could explain (`_proof.any_role_writes`) and skips only when none are left.
   A failed snapshot follows the same rule (with the recorded windows' roles), and a failed
   tree diff leaves only the preexisting paths unjudged. New test: with
   `windows_since` raising, `src/other.py` fails, named alone, with no skip. The existing
   plan-only case still skips.
5. minor, stale docstrings. `test_scope_clean_hardcoded_defaults_still_exempt` now asserts that
   a `pathly/plans/feat/PROGRESS.md` change fails after the exports and `.tsbuildinfo` pass, and
   its docstring says so. `_is_own_storage`'s docstring now describes the narrowed gate. I kept
   the test name: it still checks the hardcoded defaults (exports, `.tsbuildinfo`), and
   renaming it would read as a deleted test.
6. minor, a sub-agent the builder spawns writes inside the builder's window. I did not change
   this here, and here is why. spec.md § Decisions ("The `team/build.md` and `team/review.md`
   sub-agent fixers") chooses one sentence in `RUNNER_CONTRACT_BLOCK`: headless agents write
   the feedback file and stop, and the supervisor routes it. Ticket 10 ("The runner contract")
   owns that sentence and its test. Adding it here would edit outside this ticket and make
   ticket 10's test-first commit pass early. Until 10 lands, the risk is named in the doc's
   limits paragraph and under For later tickets below.
7. minor, a private helper reached across modules. `_proof._storage_rel` is now public
   `storage_rel`, and `scope.py` calls that. For the same reason the gate uses
   `task_proof.instant`, not `_instant`.

**For later tickets**

- 06 and 07: spec.md § Migration orders `BUILDING->REVIEWING` as the existing gates,
  `floor_gate`, `task_checks`, `scope_gate`. Insert yours before the `scope_gate` entry; the
  test `test_the_team_flows_end_building_with_the_scope_gate` asserts it is the last one. 06:
  the plan is uncommitted when BUILDING begins in a default run, so a diff from `proof_base`
  sees it only if the base tree holds the plan (a snapshot does: it includes untracked files).
- 09: `team` and `team-build` now record a `SPAWN_WINDOW` for every single-path spawn, since
  `spawn_window.wants_windows` is true for them.
- 10: when `build_baseline.tree` exists, `scope.py::_unexplained` can take it as the base
  instead of the first window's `before`, which also covers interactive runs. The
  `RUNNER_CONTRACT_BLOCK` sentence matters to this gate too: without it, a planner sub-agent
  the builder spawns edits the plan inside the builder's window and `SCOPE_VIOLATION.md`
  blames the builder.
- 13: a task's `files` now sets its scope for `scope_gate` (a directory entry covers
  everything under it), but only for a task posted before the build began and not by a
  builder.
- 14: in a headless run the scope gate now catches a builder edit to the plan whether or not
  the plan was committed. The floor gate's `plan-edit` (ticket 06) is meant to catch it too.

## Review findings (round 1, quality review)

Quality pass for build-proof 08, base 7639838573d67ac9eff6aeb31f20046349a12eba. The review stops at dafa863 (END is HEAD), so it covers every commit after the base. I read the ticket at the base commit (its Answer section was empty there) and the diff with the tasks folder held back. The Answer did not reach me. The ticket's Status changed from open to resolved.

I re-ran all three Done when commands with the dev venv on PATH, and all pass:
- `test_scope_gate_narrowed.py`: 22 passed
- `test_gates.py`: 31 passed
- `tests/fsm_flows`: 518 passed, 9 skipped

The full `tests/` suite also passes (2560 passed, 14 skipped). So do `check_file_size`, `gen_test_index --check`, `check_no_mirror_reads` and `lint-imports`. The working tree is still clean; pytest made temp dirs only under the system temp dir.

QUALITY
1. major src/pathly_orchestrator/fsm/gates/scope.py: The gate still lets the builder rewrite its own plan in an ordinary headless `team` run.
   - `_in_scope` checks `_covered(path, preexisting_dirty)` first, and a `dir/` baseline entry now covers its whole subtree.
   - In `team`, the planner writes USER_STORIES.md and IMPLEMENTATION_PLAN.md during PLANNING. Nothing commits before BUILDING: `pathly.auto_commit` is off by default, and the only commit action is on BUILDING->REVIEWING.
   - So when `fsm_ops.next_action` takes the BUILDING baseline, those files show as `?? pathly/` or `?? pathly/features/<f>/`, or as ` M <file>`. Every later builder edit to them is exempt as "preexisting".
   - That includes adding a path to the scope file, so the builder can widen its own scope. This defeats the rule "the scope file never covers its own edit".
   - The new tests commit the plan files in the `repo` fixture before the build, so this case is never exercised.
   - Fix: decide by content, not by whether the file was dirty at the baseline. One way is to count a path as the builder's when a builder `SPAWN_WINDOW` since `started_at` changed its blob (team flows now record windows); another is to compare blobs against a tree stamped in `build_baseline`. At least do this for paths under the storage dir and board home. Add a test where the plan files are untracked when the baseline is taken.
2. major src/pathly_orchestrator/CLAUDE.md: The new "Scope gate" paragraph says without condition that "a builder edit to `USER_STORIES.md` or `IMPLEMENTATION_PLAN.md` fails" and that "the scope file never covers its own edit". Per finding 1, neither holds in the default team run, and agents and humans read this doc as the contract. Make the claim true (fix finding 1), or state the limitation and record it under map.md's Open questions.
3. minor src/pathly_orchestrator/fsm/gates/scope.py (`_claimed_files`): The declared scope counts the `files` of any task claimed since `started_at`, whoever posted it. A builder can POST a new task with `files: [...]` to its own feature board, claim it, and widen its scope. Fix: ignore tasks whose stamped `author_role` is `builder`, or tasks created after `started_at`.
4. minor src/pathly_orchestrator/fsm/gates/scope.py (`_unexplained`): When the spawn windows can't be read, the whole gate skips, even for out-of-scope paths outside `pathly/` that no role's `stage_writes` could ever cover (so no window could explain them). Fix: skip only when an affected path is one that a window could have explained.
5. minor tests/telemetry/test_observability.py and src/pathly_orchestrator/runner/provenance.py: The `test_scope_clean_hardcoded_defaults_still_exempt` docstring still says "pathly/plans/ ... remain exempt". The test now passes only because `EVENTS.jsonl` is an export file. The `_is_own_storage` docstring in provenance.py still says the scope gate exempts `pathly/features/` and `pathly/plans/`. Update both: make the test assert that a plan file fails, and fix the docstring.
6. minor src/pathly_data/core/skills/team/build.md, a risk to the wiring: team/build tells the builder stage to spawn `planner`/`architect` itself when IMPL_QUESTIONS.md or DESIGN_QUESTIONS.md is open. An in-process subagent has no `SPAWN_WINDOW` of its own; its plan edit lands inside the builder's window. So once the plan is clean (or finding 1 is fixed), that edit is blamed on the builder. The SCOPE_VIOLATION text then tells the builder to undo the planner's clarifications. Fix: say in the runner prompt that feedback routing is the supervisor's job, or attribute subagent writes some other way.
7. minor src/pathly_orchestrator/fsm/gates/scope.py: `_out_of_scope` reaches into the private `_proof._storage_rel`. Expose a public helper instead.

REVIEW: FAIL
