# Record what each stage spawn changed and what each role may write

Type: task
Status: open
Blocked by: 02
Test first: yes

The floor, scope and reviewer gates must tell who wrote a file. In `team` and `team-build`, a
planner or architect routed a feedback file may legitimately edit `IMPLEMENTATION_PLAN.md` while
the FSM is still in BUILDING. A reviewer may write `REVIEW.md` and nothing else. This ticket
records the evidence and the rules. It adds no gate.

New `src/pathly_orchestrator/supervisor/spawn_window.py`:

- `wants_windows(flow_config)`: true when any transition in the flow's `gates` has a gate of
  type `floor_gate`, `scope_gate` or `reviewer_unchanged`.
- `observe(state, flow_config, role, run_id, spawn)`: when `wants_windows` is true and the
  project is a git repo, take `proof.tree.snapshot` and `proof.tree.head` before and after
  calling `spawn()`. Then append a `SPAWN_WINDOW` event
  `{role, run_id, state, before, after, head_before, head_after}` to the run's storage path
  (`state.storage_path`, else `fsm_ops._resolve_storage_path(None, state.project_root,
  state.topic)`) through `eventlog.append_event`. Return the spawn's result unchanged. If
  `spawn()` raises, the exception propagates and no event is written. Any snapshot or event
  failure is logged and swallowed.

Wire it at the two single-path spawn sites:

- `fan_out.run_stage`, the no-`parallel_states` branch. The role is the flow's
  `role_map[state_name]`.
- `orchestrator_stage._resolve_stage_supervised`, the feedback spawn. The role is `target` (the
  feedback's `target_agent`). Load the flow with `fan_out.load_flow_config(flow, project_root)`.

Pass the role explicitly: `terminal_identity._spawn_role` would mint a feedback builder inside
REVIEWING as `reviewer`.

New `src/pathly_orchestrator/fsm/gates/_proof.py`. It is shared by the gates, never imports
`supervisor`, and keeps its `db` imports lazy:

- `board_home(storage_path) -> str`: the repo-relative prefix the plan lives under, ending in
  `/`. That is `pathly/features/<feature>/` for a feature or goal storage dir, else the storage
  dir itself (legacy `pathly/plans/<name>/`, `pathly/project/...`).
- `stage_writes(storage_path, role) -> Callable[[str], bool]`: the paths a role may change.
  - Every role: `<storage>/feedback/**`; the server's export files (`STATE.json`,
    `BOARD.json`, `EVENTS.jsonl`) anywhere under `pathly/`, because the server rewrites them
    during a run and a user project may not gitignore them; and any `*.tsbuildinfo`.
  - `builder`: also `<storage>/VERIFY.md`.
  - `reviewer`: also `<storage>/REVIEW.md`.
  - `po`, `planner`, `architect`, `designer` (the keys of
    `fsm_compose_tables._FIX_MODE_ARTIFACT`) and `retro`: also any file directly inside the
    storage dir or the board home (the plan documents).
- `windows_since(storage_path, since=None, roles=None)`: `SPAWN_WINDOW` events from
  `eventlog.read_events` with `ts >= since`, optionally filtered by role, oldest first. Compare
  parsed datetimes, not strings: an event `ts` is `%Y-%m-%dT%H:%M:%SZ` and the stamps passed as
  `since` (`build_baseline.started_at`, `proof_base.started_at`) are `isoformat()` with an
  offset. `datetime.fromisoformat` reads both on Python 3.11, the oldest version CI runs.
- `explained(project_root, path, now_tree, windows, storage_path) -> bool`: true when some window
  whose role may write `path` left it at the blob it has in `now_tree` (`proof.tree.blob`; a
  deletion matches a deletion).
- `floor_enabled() -> bool`: the `floor.enabled` app setting; on unless it is `false`, `0` or
  `off`.

Living docs: in `src/pathly_orchestrator/CLAUDE.md`, the `SPAWN_WINDOW` event, which spawns
record it, and the role write table.

## Not in this ticket

- Gates that read the windows: tickets 06 (floor), 08 (scope) and 09 (reviewer).
- Per-task windows in the goal-loop drain: ticket 05 takes its own snapshots inside the drain.
- The run-wide `proof_base` stamp and the `TASK_PROOF` records: ticket 15.

## Done when

- `python -m pytest tests/runner_supervisor/test_spawn_window.py -q -p no:cacheprovider` passes.
  It uses a `git init` repo under `tmp_path` and a fake spawn that edits a file. It covers:
  `observe` writes one `SPAWN_WINDOW` with the given role and two different trees; a flow with
  no such gate writes none; a spawn that raises writes none and re-raises; outside a git repo
  it writes none and returns the result. A `fan_out.run_stage` call on a `team-build` flow
  config records role `builder` for BUILDING.
- `python -m pytest tests/fsm_flows/test_gates_proof_helpers.py -q -p no:cacheprovider` passes.
  It covers: `board_home` for a feature, a goal and a project storage dir; `stage_writes` for
  builder, reviewer and planner on `VERIFY.md`, `REVIEW.md`, `IMPLEMENTATION_PLAN.md` and
  `feedback/X.md`; `explained` is true for a plan file left as a planner window left it and
  false after a later edit; `windows_since` with an `isoformat()` `since` keeps a window whose
  `ts` is later and drops one whose `ts` is a second or more earlier; `floor_enabled` with the
  setting unset, `false` and `true`.

```check
# The conductor runs this block before review.
$ python -m pytest tests/runner_supervisor/test_spawn_window.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/fsm_flows/test_gates_proof_helpers.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- spec.md § Decisions ("Telling an upstream role's legitimate plan edit from the builder's",
  "What a reviewer may not change"), § Interfaces (events)
- `src/pathly_orchestrator/supervisor/fan_out.py::run_stage`,
  `supervisor/orchestrator_stage.py::_resolve_stage_supervised` (the `_run_stage_via_terminal`
  call under `# ── Blocked / feedback`)
- `src/pathly_orchestrator/eventlog.py::append_event`, `read_events`
- `src/pathly_orchestrator/fsm_compose_tables.py::_FIX_MODE_ARTIFACT`

## Answer
