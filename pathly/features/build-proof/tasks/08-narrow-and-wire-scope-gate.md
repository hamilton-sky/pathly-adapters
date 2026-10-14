# Narrow scope_gate to what a stage may write and wire it into the team flows

Type: task
Status: open
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
