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

Work started at commit `7639838573d67ac9eff6aeb31f20046349a12eba`. Test-only commit: `fc72758`
(`test(build-proof): 08 failing test`). At that commit the three test files gave `24 failed,
51 passed`, every failure an assertion on behaviour: 21 of the 22 new cases (the old gate
ignores task `files`, so a change inside a claimed task's files failed; the blanket
`pathly/features/` exemption let a `USER_STORIES.md` edit and a self-widening scope file through
(`_failed(None)`); the failure text was only "changes outside declared scope in
IMPLEMENTATION_PLAN.md"; the packaged flows' last `BUILDING->REVIEWING` gate was `command_gate`).
The one pass was `test_goal_loop_does_not_carry_the_scope_gate`. In `test_gates.py` the builder
plan-edit case passed the gate and the codebase case's text did not name `src/out_of_scope.py`;
`test_spawn_window.py` read `wants_windows(team-build)` as `False`.

**Built**

- `src/pathly_orchestrator/fsm/gates/scope.py` (172 → 342 lines). `check_scope_gate` reads
  `gate.get("scope_file")` (optional) and declares the union of its backtick paths and the
  `files` of the tasks from `task_proof.tasks_claimed_since(get_db(), board, feature_scope,
  goal_id, build_baseline.started_at)` (`_claimed_files`, `_task_files`). `_covered` makes an
  entry cover itself and everything under it, with or without a trailing `/`. `_out_of_scope`
  drops `preexisting_dirty`, `_proof.stage_writes(storage, "builder")` (feedback, `VERIFY.md`,
  exports, `*.tsbuildinfo`), `scope_gate.exempt_prefixes` and declared paths (the scope file
  never covers its own edit); `_unexplained` then drops what `_proof.explained` attributes to a
  `SPAWN_WINDOW` since `started_at`, taking `tree.snapshot` only when a window's role may write
  a remaining path. `_failure_text` lists at most 20 paths, then `- ... and N more`.
  `_git_dirty` lists untracked files one by one (`--untracked-files=all`). `_scope_clean` keeps
  its signature as the boolean form (scope file only). The blanket `pathly/features/` and
  `pathly/plans/` exemption is gone.
- `src/pathly_data/core/flows/team.flow.yaml`, `team-build.flow.yaml`: `{type: scope_gate,
  scope_file: IMPLEMENTATION_PLAN.md, on_fail: SCOPE_VIOLATION.md}` as the last
  `BUILDING->REVIEWING` gate, with a comment. Both already route `SCOPE_VIOLATION: builder`.
- `src/pathly_orchestrator/fsm_compose_responses.py::_exit_requirement`: the `scope_gate` line
  now names the paths in the scope file plus the claimed tasks' `files`, the feedback files and
  `VERIFY.md`, and says any other change, a plan file included, fails the gate.
- `src/pathly_orchestrator/CLAUDE.md`: the `scope_gate` row of the gate table; a "Scope gate"
  paragraph (declared, changed paths, exempt, skips, wired into both team flows, not goal-loop);
  the spawn-window paragraph no longer says no flow records windows and no gate reads them; the
  provenance paragraph no longer quotes the old `pathly/features/`/`pathly/plans/` prefix check.
- Tests (in the test-only commit, then the setup folded into a `_build` helper):
  `tests/fsm_flows/test_scope_gate_narrowed.py` (new, 22 cases, 387 lines); the three
  `test_scope_gate_plan_files_*` tests in `tests/fsm_flows/test_gates.py` rewritten
  (`..._edited_by_the_builder_fail`, `..._feedback_and_verify_pass`,
  `..._do_not_mask_undeclared_codebase`); `tests/runner_supervisor/test_spawn_window.py`'s
  assertion that the packaged `team-build` wants no windows flipped to `True` (its docstring
  said that would change with ticket 08); regenerated `tests/INDEX.md`, `tests/fsm_flows/INDEX.md`.

**Proof** (each run fresh after the last edit)

- `python -m pytest tests/fsm_flows/test_scope_gate_narrowed.py -q -p no:cacheprovider`:
  `22 passed in 9.06s`, exit 0. In a `git init` repo under `tmp_path`, with `build_baseline`
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
  - also: the scope file's paths and the task files form one union; a task claimed before
    `started_at` declares nothing; a goal run reads only its goal's tasks; declared files in a
    new untracked folder pass and an undeclared third file there fails; a preexisting
    `scratch/` entry covers `scratch/notes.txt`; a builder adding `` `pathly/` `` to the scope
    file still fails on that file; `docs/` (exempt prefix) and a `.tsbuildinfo` pass; an
    exception from `windows_since` skips with `spawn_windows_unreadable`; 25 undeclared files
    name 20 (`extra_00` .. `extra_19`) and `5 more`; `team` and `team-build` end
    `BUILDING->REVIEWING` with the scope gate and route `SCOPE_VIOLATION` to `builder`, and
    their BUILDING exit requirement names `` `IMPLEMENTATION_PLAN.md` `` and `` `files` ``;
    `goal-loop` carries no `scope_gate`.
- `python -m pytest tests/fsm_flows/test_gates.py -q -p no:cacheprovider`: `31 passed in
  6.15s`, exit 0, with the three rewritten tests: a builder edit to
  `CONVERSATION_PROMPTS.md` / `PROGRESS.md` in its storage fails and the text names both (not
  `src/app.py`); `feedback/IMPL_QUESTIONS.md` and `VERIFY.md` pass; `src/out_of_scope.py`
  still fails and is named, `VERIFY.md` is not.
- `python -m pytest tests/fsm_flows -q -p no:cacheprovider`: `518 passed, 9 skipped in
  85.89s`, exit 0 (the 9 skips are existing ones; none are in the files this ticket touched).
- The check block: the same three commands, each exit 0 and printing `passed`.
- Test (`python -m pytest tests/ -q -x -p no:cacheprovider`): `2560 passed, 14 skipped in
  432.27s`, exit 0.
- Lint (the full chain in `commands.md`): exit 0. black `504 files would be left unchanged`;
  mypy `Success: no issues found in 285 source files`; file size `945 source files checked; 19
  known over 400 lines, none new, none grown`; mirror reads OK; `All test INDEX.md files up to
  date.`; lint-imports `Contracts: 1 kept, 0 broken.`; bandit no issues (only the existing
  `nosec` notices); adapters OK; `Entry points OK: 16 checked`.
- Smoke: exit 0. Build (`python -m build --wheel`): `Successfully built
  pathly_adapters-2.24.1-py3-none-any.whl`, exit 0.

**Decisions**

- Untracked files are listed one by one (`git status --porcelain=v1 --untracked-files=all`).
  Without it git names a wholly new folder as one `?? src/newpkg/` line, which a declared
  `src/newpkg/a.py` never matches, and a new goal storage dir shows as one `?? .../goals/`
  line that `stage_writes` cannot recognise. With the blanket storage exemption gone, both
  became false failures. `fsm_ops`' `preexisting_dirty` still stores the collapsed form, so a
  baseline entry is matched with the same `_covered` rule: a `dir/` entry covers the files
  under it, as the old exact match of two collapsed lines did.
- The scope file never covers its own edit. Otherwise a builder could add `` `pathly/` `` (or
  any parent dir) to `IMPLEMENTATION_PLAN.md` and pass the gate with that very edit. A planner
  or architect edit to it is still excused through its window.
- Fail open, as the module always has: `tasks_unreadable` (a DB error reading the claimed
  tasks, or a `started_at` that is not a time), `spawn_windows_unreadable` (any exception from
  `windows_since`), `snapshot_failed` (the now-snapshot is `None`, for example a project inside
  a larger repo) each log a `GATE_SKIPPED` and allow the transition. `git_diff_failed`,
  `no_build_baseline`, `no_declared_scope` and `GATE_DEGRADED` are unchanged.
- The snapshot is taken only for a path some window's role may write. `explained` can only
  excuse such a path, so a code file outside the scope never costs a snapshot or a blob lookup,
  and windows are read once per gate, only when a path is outside the scope.
- `.tsbuildinfo` needs no separate check: `stage_writes` grants it to every role.
- No `started_at` in the baseline: no task files are read (there is no window to read them in)
  and `windows_since` gets `since=None` (every window). `fsm_ops` always stamps it; only
  hand-written baselines in older tests lack it.
- `_scope_clean(storage, scope_file, preexisting, flow)` stays, with the narrowed rule and
  only the scope file declared: `fsm/__init__`, `fsm/engine.py`, `fsm/engine_actions.py` and
  `gates/__init__` re-export it and `tests/telemetry/test_observability.py` calls it.
- `_task_files` parses the `files` JSON in `scope.py`. `supervisor/lane_partition._declared_files`
  does the same, but `fsm/gates` may not import `supervisor`.
- In a goal run the tasks are goal-scoped (`tasks_claimed_since` ignores board and scope when
  `goal_id` is set), the same rule as `require_tasks_done`.

**Shortcuts taken**

- `preexisting_dirty` is path-level. A path that was dirty when BUILDING began is never
  judged, even if the builder changes it again. With `auto_commit` off, an uncommitted plan
  (or a collapsed `?? pathly/` line on a fresh project) is preexisting, so the scope gate does
  not see a builder's plan edit there. The floor gate's `plan-edit` (ticket 06, a tree diff
  since `proof_base`) covers that case. Worth upgrading when `build_baseline.tree` exists
  (ticket 10): diff that tree against a now-snapshot instead of subtracting paths.
- A task claimed in an earlier BUILDING does not declare scope for a later BUILDING after a
  `REVIEWING->BUILDING` back-edge (the ticket's window is `build_baseline.started_at`, which is
  re-stamped). The files that task already dirtied are preexisting by then, so only a new file
  the fix round creates outside the scope file is at risk of a false failure.
- `git diff --name-only HEAD` (unchanged) lists only the new name of a staged rename and fails
  in a repo with no commits (the gate then skips). Left as it was.
- Two comments outside this ticket now read slightly stale and were left alone:
  `tests/telemetry/test_observability.py::test_scope_clean_hardcoded_defaults_still_exempt`'s
  docstring says `pathly/plans/` stays exempt (the test still passes because its path is an
  `EVENTS.jsonl` export), and `runner/provenance.py::_is_own_storage`'s docstring quotes the old
  `_scope_clean` prefixes.

**For later tickets**

- 06 and 07: spec.md § Migration orders `BUILDING->REVIEWING` as the existing gates,
  `floor_gate`, `task_checks`, `scope_gate`. Insert yours before the `scope_gate` entry; the
  test `test_the_team_flows_end_building_with_the_scope_gate` asserts it is the last one.
- 09: `team` and `team-build` now record a `SPAWN_WINDOW` for every single-path spawn, since
  `spawn_window.wants_windows` is true for them.
- 13: a task's `files` now sets its scope for `scope_gate`; a directory entry covers
  everything under it.
- 14: in the acceptance run, "a builder that edits the plan is caught" is the floor gate's job
  when the plan was already dirty at BUILDING entry (see the first shortcut); the scope gate
  catches it when the plan was committed.
