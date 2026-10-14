# Record what each stage spawn changed and what each role may write

Type: task
Status: resolved
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

Work started at commit `a9a55752a1d45a88fef9cf811b487567ebb7efc6`. Test-only commit: `145577b`
(`test(build-proof): 04 failing test`). At that commit both Done-when commands fail at collection
with `ImportError: cannot import name 'spawn_window' from 'pathly_orchestrator.supervisor'` and
`ImportError: cannot import name '_proof' from 'pathly_orchestrator.fsm.gates'` (exit 2).

**Built**

- `src/pathly_orchestrator/supervisor/spawn_window.py` (new, 138 lines): `WINDOW_GATES`,
  `wants_windows(flow_config)`, `observe(state, flow_config, role, run_id, spawn)`.
- `src/pathly_orchestrator/supervisor/fan_out.py`: `run_stage`'s no-`parallel_states` branch
  passes the spawn through `observe` with role `role_map[state_name]` (`""` when the flow has
  none). The arguments `_run_stage_via_terminal` gets are unchanged.
- `src/pathly_orchestrator/supervisor/orchestrator_stage.py`: the feedback spawn under
  `# ── Blocked / feedback` goes through `observe` with role `target` and the flow from
  `fan_out.load_flow_config(flow, project_root)`.
- `src/pathly_orchestrator/fsm/gates/_proof.py` (new, 174 lines): `EXPORT_FILES`, `PLAN_ROLES`,
  `board_home`, `stage_writes`, `windows_since`, `explained`, `floor_enabled`. It imports
  `proof.tree`, `fsm_compose_tables._FIX_MODE_ARTIFACT` and `gates._helpers` at the top, and
  `db` and `eventlog` only inside functions.
- `src/pathly_orchestrator/CLAUDE.md`: a `spawn_window.py` entry in the package map, and a
  "Spawn windows and stage writes" paragraph in § Transition gates: the `SPAWN_WINDOW` event, the
  two spawns that record it and with which role, the role write table, and `explained`,
  `windows_since` and `floor_enabled`.
- Tests: `tests/runner_supervisor/test_spawn_window.py` (new, 22 cases),
  `tests/fsm_flows/test_gates_proof_helpers.py` (new, 44 cases), regenerated `tests/INDEX.md`,
  `tests/fsm_flows/INDEX.md` and `tests/runner_supervisor/INDEX.md`.

**Proof** (each run fresh after the last edit)

- `python -m pytest tests/runner_supervisor/test_spawn_window.py -q -p no:cacheprovider`:
  `22 passed in 5.11s`, exit 0. Every case uses a `git init` repo under `tmp_path` (with a git
  identity) and a fake spawn that edits a file:
  - `observe` with a `floor_gate` flow returns the spawn's own result object and writes exactly
    one `SPAWN_WINDOW` with `role == "builder"`, `run_id`, `state == "BUILDING"`, and
    `before != after`, where `tree.changes(before, after) == [("M", "src/app.py")]`, plus
    `head_before == head_after ==` `git rev-parse HEAD`. A spawn that commits gives
    `head_after != head_before`.
  - A flow with only `command_gate` writes none and takes no snapshot (a counting
    `tree.snapshot` saw 0 calls).
  - A spawn that raises `RuntimeError` is re-raised (`pytest.raises`) and writes none.
  - Outside a git repo, `observe` writes none and returns the result, and the spawn's edit is on
    disk.
  - A raising `tree.snapshot` or `eventlog.append_event` is swallowed: the result is returned and
    no window is written.
  - With `storage_path=""`, the window lands in `_resolve_storage_path(None, root, "demo")`.
  - `wants_windows` is true for each of the three gate types, on an edge key and on a `->DONE`
    key. It is false for `None`, `{}`, empty `gates`, `command_gate` only, a `None` gate list,
    and the top-level `scope_gate:` config key.
  - `fan_out.run_stage` on the packaged `team-build` flow config, with a `floor_gate` added to
    `BUILDING->REVIEWING`, records `role == "builder"` and `state == "BUILDING"`. The spawn got
    the identical positional arguments plus `session`/`autonomy`.
  - `_resolve_stage_supervised`, blocked on `IMPL_QUESTIONS.md` routed to `planner` while in
    REVIEWING (the flow's `role_map` says `reviewer`), records `role == "planner"`,
    `state == "REVIEWING"` and `run_id` `demo-fb1-…`, and the window changed only
    `IMPLEMENTATION_PLAN.md`.
- `python -m pytest tests/fsm_flows/test_gates_proof_helpers.py -q -p no:cacheprovider`:
  `44 passed in 5.28s`, exit 0. Covers:
  - `board_home` gives `pathly/features/demo/` for both `pathly/features/demo` and
    `pathly/features/demo/goals/add-export`, `pathly/project/goals/add-export/` for a project
    goal, `pathly/project/` and `pathly/plans/legacy/` (from a `Path` and from a `str`).
  - `stage_writes` on `VERIFY.md` / `REVIEW.md` / `IMPLEMENTATION_PLAN.md` / `feedback/X.md`:
    builder T/F/F/T, reviewer F/T/F/T, planner T/T/T/T. `po`, `architect`, `designer`, `retro`
    and `Planner` may write the plan documents but not a subfolder, another feature's plan or
    `src/`. Every role may write nested feedback, `STATE.json`/`EVENTS.jsonl`/`BOARD.json` under
    `pathly/`, and `*.tsbuildinfo`, but not `src/STATE.json`. In a goal run, the planner may
    write the board-home plan and the goal dir, and the builder only the goal dir's `VERIFY.md`
    and feedback.
  - `explained` is true for a plan file left as a planner window left it, and false after a
    later builder edit. It is false when the window's role may not write the path (builder), and
    false for a builder edit made before a planner window that never touched the file (that
    window's new `ARCHITECTURE_PROPOSAL.md` is explained). A `po` deletion matches a deletion and
    stops matching once the file is restored. No `now_tree`, no windows, or a window without
    `before` explain nothing.
  - `windows_since` with `since =` `isoformat()` of 12:00:00.25 UTC written with a `+02:00`
    offset drops a window at `11:59:59Z`. It keeps `12:00:00Z`, `12:00:01Z` and `12:00:02Z`
    oldest first (one was appended out of order), and leaves out a non-window event. A string
    compare would have dropped all three, since `"…T12…" < "…T14…"`. It also filters by role
    (`["reviewer"]`, `"builder"`, `{"planner"}`), keeps everything without `since`, and raises
    `ValueError` for `"yesterday"`.
  - `floor_enabled` is true unset, false for `false`/`0`/`off`/`False`/` OFF `, and true for
    `true`/`1`/`on`/`yes`.
- The check block: the same two commands, both exit 0 and print `passed` (above).
- Test (`python -m pytest tests/ -q -x -p no:cacheprovider`): `2538 passed, 14 skipped in
  438.45s`, exit 0.
- Lint (the full chain in `commands.md`): exit 0. black `503 files would be left unchanged`;
  mypy `Success: no issues found in 285 source files`; file size `945 source files checked; 19
  known over 400 lines, none new, none grown`; mirror reads OK; `All test INDEX.md files up to
  date.`; lint-imports `Contracts: 1 kept, 0 broken.`; bandit reported no issues (only the
  existing `nosec` warnings in other files); adapters OK; entry points OK.
- Smoke: exit 0. Build (`python -m build --wheel`): `Successfully built
  pathly_adapters-2.24.1-py3-none-any.whl`, exit 0.

**Decisions**

- `explained` also requires the window to have changed the path itself: its blob in `before`
  differs from its blob in `after`. Read literally, "left it at the blob it has in `now_tree`"
  would let a planner window that never touched the plan excuse a builder edit made before it,
  because that window's after-tree holds the builder's text. The spec chose windows over
  re-baselining because re-baselining "would also excuse a builder edit made before the planner
  ran", so the window has to be the one that wrote the content. A deletion still matches a
  deletion: the window removed the file and it is absent now. Pinned by
  `test_a_planner_window_that_left_the_file_alone_does_not_excuse_an_earlier_edit`.
- `windows_since` cuts `since` to its whole second. Event `ts` has whole seconds
  (`eventlog._now()`), so an event appended 0.7 s into the second `since` was stamped in would
  read as earlier and be dropped. Keeping same-second windows can take in one stamped up to a
  second before `since`. It can only excuse a change that window really made, so it is
  harmless. A `since` that is not a time raises `ValueError`, the same contract as ticket 03's
  `*_since`. Times are parsed by `db.queries.task_proof._instant`, imported lazily, so there is
  no second parser (CLAUDE.md rule 5). Windows are sorted by parsed `ts` (a stable sort), so
  same-second windows keep the order they were appended in.
- `observe` writes no window when either snapshot is missing: not a git repo top, git failed,
  or an exception. It logs a missing before-snapshot at info, and exceptions at warning. A
  window with `after: None` would give a gate nothing to compare. `role` and `run_id` are stored
  as passed, and `state` is `state.current_state`.
- The window is appended with `create_dir=False`. The event is DB-backed, and the fallback
  storage path (`_resolve_storage_path(None, root, topic)`) may not exist for debug or goal runs,
  so this plants no decoy dir for `_resolve_storage_path`'s existence probe (the same reason as
  `context_record.py`).
- `wants_windows` reads only the transitions in `gates`, wildcard `->X` keys included. The
  top-level `scope_gate:` key in `team-build` (`exempt_prefixes`) is config, not a gate.
- `stage_writes` lower-cases the role. An empty or unknown role gets only the every-role set.
  `board_home` and the storage prefix are taken relative to `gates._helpers.project_root_of`
  (the event log's root rule), so they agree with the root the gates run git in. An empty prefix
  (storage dir == project root) grants nothing.
- `floor_enabled`: a DB read error keeps the floor on, and is logged.
- The feedback site loads the flow at each feedback spawn, not once per stage, so a stage with
  no feedback costs no extra DB read, and `orchestrator.py` (399 lines) is untouched.
- The fan-out test adds a `floor_gate` to a copy of the packaged `team-build` flow. The packaged
  flow has none of the three gates until tickets 06, 08 and 09, so as shipped it records no
  windows, and the test asserts that too.

**Shortcuts taken**

- `explained` compares blob ids from `tree.blob`, which returns `None` both for an absent path
  and when git fails. Suppose git failed on both the after-tree read and the now-tree read, but
  not on the before-tree read. A path the window did not delete would then read as deleted by
  the window and be excused. That takes two failed sub-second `rev-parse` calls in a row. Worth a
  `blob_or_none` (absent vs failed) in `proof/tree.py` if gates ever see git time out.
- Each `tree.blob` call runs its own `--show-toplevel` check. So `explained` costs about
  2 + 4 × (windows whose role may write the path) git processes per path. That is fine for a
  handful of plan files. Worth batching (one `changes` per window, cached by tree ids) if a gate
  ever explains many paths.

**For later tickets**

- Use `from pathly_orchestrator.fsm.gates import _proof`. Ticket 06 can build floor's
  `may_change` as
  `lambda p: _proof.explained(root, p, after, _proof.windows_since(storage, base["started_at"]), storage)`.
  Read the windows once per gate, not once per path.
- `windows_since` raises `ValueError` for a bad `since`, and lets a DB error from
  `eventlog.read_events` propagate. A gate that must fail open should catch both.
- A window is recorded only while `spawn_window.wants_windows(flow)` is true, so a run records
  windows only after a flow YAML carries `floor_gate`, `scope_gate` or `reviewer_unchanged`
  (tickets 06, 08 and 09). A new gate type that reads windows must be added to
  `spawn_window.WINDOW_GATES`.
- A window's `role` is what the caller passed: the flow's `role_map` entry (`builder`,
  `reviewer`, `tester`, `retro` in the team flows) or the feedback `target_agent`. A
  `REVIEW_INCOMPLETE` feedback spawn routes to `reviewer`, so it is recorded as a reviewer
  window too. Ticket 09 should filter with `roles={"reviewer"}`, and must expect `head_before` /
  `head_after` to be `None` in a repo with no commits yet.
- Every event append rewrites the storage dir's `EVENTS.jsonl` about 0.5 s later. A whole-run
  diff will show it, and `stage_writes` allows it for every role.
