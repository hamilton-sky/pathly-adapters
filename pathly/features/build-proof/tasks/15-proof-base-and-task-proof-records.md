# Stamp a run-wide proof base and record task proofs

Type: task
Status: resolved
Blocked by: 02
Test first: yes

The floor gate and the task-check gate judge the whole run, not one stage: builder fix rounds
run inside REVIEWING, TESTING, RETRO and after the goal-loop drain, and `build_baseline` is
popped on every transition. They need one base that lasts the run, and a record of which task
completions were already proven, so a task is checked once and a fix round's task is not
missed. This ticket adds both. It adds no gate.

New `src/pathly_orchestrator/fsm/gates/_proof_record.py`. It never imports `supervisor`, keeps
its `db` and `eventlog` imports lazy, and reads state through `eventlog.read_state` (the DB)
only, with no `STATE.json` fallback, so `scripts/check_no_mirror_reads.py` needs no allow-list
entry.

- `wants_proof_base(flow_config, state_name) -> bool`: true when a gate list for an edge out of
  `state_name` holds a gate of type `floor_gate` or `task_checks`. The edges are the
  `<state>->X` keys and the wildcard `->X` keys for every `X` in `transitions[state_name]`.
- `stamp_proof_base(prior_state, flow_config, state_name, project_root) -> dict | None`: when
  `wants_proof_base` is true and `prior_state` has no `proof_base`, return
  `{"tree": proof.tree.snapshot(project_root), "started_at": <datetime.now(timezone.utc).isoformat()>}`.
  `tree` is `None` when the snapshot is (not a git repo); `started_at` is always set, because
  the task-check gate needs it without git. Otherwise return `None`.
- `read_proof_base(storage_path) -> dict | None`.
- `record_task_proof(storage_path, task, run_id, checks, floor, warnings=())`: append
  `TASK_PROOF {task_id, claimed_at, run_id, checks, floor, warnings}` through
  `eventlog.append_event`, with `claimed_at` copied from the task row. `checks` is one of
  `passed`, `failed`, `none`, `error`; `floor` is one of `clean`, `failed`, `off`, `n/a`.
- `task_proven(storage_path, task) -> bool`: true when the newest `TASK_PROOF` for `task["id"]`
  has the task's current `claimed_at`, `checks` in (`passed`, `none`) and `floor` not `failed`.
  A re-claimed task (a retry or a human re-open sets a new `claimed_at`) is not proven.

Wire the stamp:

- in `fsm_ops.next_action`, right after the existing `build_baseline` stamp: when
  `stamp_proof_base(...)` returns a dict, put it in `stamped_state["proof_base"]` and set
  `needs_write`. A few lines; the logic stays in `_proof_record.py`;
- in `fsm_ops_complete`, next to the `prior_state.pop("build_baseline", None)` line: pop
  `proof_base` only when `next_state == "DONE"`. Every other transition keeps it, so a
  back-edge (REVIEWING->BUILDING) and a resumed run keep the first base.

Living docs: in `src/pathly_orchestrator/CLAUDE.md`, the `proof_base` STATE key (when it is
stamped, that it lasts until DONE) and the `TASK_PROOF` event.

## Not in this ticket

- The gates that read `proof_base` and `TASK_PROOF`: the floor gate and the task-check gate
  (tickets 06 and 07).
- Writing `TASK_PROOF` from the goal-loop drain: ticket 05.
- The per-stage `build_baseline.tree` and `review_base` used for the Review packet: ticket 10.

## Done when

- `python -m pytest tests/fsm_flows/test_proof_base.py -q -p no:cacheprovider` passes. It
  covers, in a `git init` project under `tmp_path`:
  - `wants_proof_base` on dict flow configs: true for a state with an outgoing `floor_gate`,
    true through a `->DONE` wildcard, false for a state with neither type;
  - `fsm_ops.next_action` on the packaged `team-build` flow, with `fsm_ops._load_flow` patched
    to return it plus one `{type: floor_gate}` on `BUILDING->REVIEWING`, stamps `proof_base`
    with a tree and a `started_at`; a second call keeps the first value; the same on
    `goal-loop` with a gate added to `DRAINING->DONE` stamps it on DRAINING;
  - outside a git repo the stamp has `tree` `None` and a `started_at`;
  - `complete_stage` from BUILDING to REVIEWING keeps `proof_base`, and a transition into DONE
    drops it;
  - `task_proven` is true after a passing `record_task_proof`, false after the task is claimed
    again, and false when `floor` was `failed`.
- `python scripts/check_no_mirror_reads.py` exits 0.

```check
# The conductor runs this block before review.
$ python -m pytest tests/fsm_flows/test_proof_base.py -q -p no:cacheprovider
exit 0
prints passed
$ python scripts/check_no_mirror_reads.py
exit 0
```

## Reference

- spec.md § Decisions ("The diff base for the floor gate", "When task checks run"), § Interfaces
  (STATE keys, events)
- `src/pathly_orchestrator/fsm_ops.py::next_action` (the `build_baseline` stamp),
  `fsm_ops_complete.py` (the `prior_state.pop("build_baseline", None)` line)
- `src/pathly_orchestrator/eventlog.py` (`read_state`, `append_event`, `read_events`)
- `src/pathly_orchestrator/fsm/gates/scope.py::_read_build_baseline` (the pattern; this one
  drops the disk fallback)

## Answer

Work started at commit `df918c3f28508ba18a6c98e8c634a29265209f6a`. Test-only commit: `520a7f6`
(`test(build-proof): 15 failing test`, the new test file plus the regenerated
`tests/INDEX.md` and `tests/fsm_flows/INDEX.md`). At that commit
`python -m pytest tests/fsm_flows/test_proof_base.py -q -p no:cacheprovider` fails at
collection (`ImportError: cannot import name '_proof_record' from
'pathly_orchestrator.fsm.gates'`, exit 2). Two tests in it were wrong, not the code (it used
`tree.blob`, which returns a blob id, where `tree.read` gives the text, and the back-edge test
sent no `goal_id`, which `on_board_count` needs); I fixed both in the code commit.

**Built**

- `src/pathly_orchestrator/fsm/gates/_proof_record.py` (new, 134 lines). Imports `proof.tree` at
  the top; `eventlog` (and so `db`) lazily inside `read_proof_base`, `record_task_proof` and
  `task_proven`; never `supervisor`. It reads state through `eventlog.read_state` only, so
  `scripts/check_no_mirror_reads.py` needed no allow-list line.
  - `wants_proof_base(flow_config, state_name)`: true when `gates["<state>-><X>"]` or
    `gates["-><X>"]`, for any `X` in `transitions[state_name]`, holds a gate whose `type` is
    `floor_gate` or `task_checks` (`PROOF_GATES`).
  - `stamp_proof_base(prior_state, flow_config, state_name, project_root)`: `None` when
    `prior_state["proof_base"]` is set or the state wants none, else
    `{"tree": proof.tree.snapshot(project_root), "started_at": datetime.now(timezone.utc).isoformat()}`
    (`tree` is `None` outside a git repo).
  - `read_proof_base(storage_path)`: the stored dict, else `None`.
  - `record_task_proof(storage_path, task, run_id, checks, floor, warnings=())`: appends
    `TASK_PROOF {task_id, claimed_at, run_id, checks, floor, warnings}` through
    `eventlog.append_event`, `claimed_at` copied from the task row.
  - `task_proven(storage_path, task)`: the newest `TASK_PROOF` for `task["id"]` (highest `seq`)
    has the task's current `claimed_at`, `checks` in (`passed`, `none`) and `floor` not `failed`.
- `src/pathly_orchestrator/fsm_ops.py` (342 to 351 lines): `next_action` calls
  `stamp_proof_base(prior_state, flow_config, state_info["current_state"], project_root)` right
  after the `build_baseline` stamp and, when it returns a dict, puts it in
  `stamped_state["proof_base"]` and sets `needs_write`; one new import.
- `src/pathly_orchestrator/fsm_ops_complete.py` (333 to 336 lines): `if next_state == "DONE":
  prior_state.pop("proof_base", None)` next to the `build_baseline` pop.
- `src/pathly_orchestrator/CLAUDE.md`: a "Proof base and task proofs" paragraph under the
  Transition gates section, after the Floor guard paragraph (the `proof_base` STATE key: when it
  is stamped, that it lasts until DONE; the `TASK_PROOF` event and the two functions).
- `tests/fsm_flows/test_proof_base.py` (new, 34 tests; reuses the `repo`/`flow` fixtures and
  helpers of `review_packet_support`), regenerated `tests/INDEX.md` and `tests/fsm_flows/INDEX.md`.

**Proof** (each run fresh, after the last code edit)

- `python -m pytest tests/fsm_flows/test_proof_base.py -q -p no:cacheprovider`: `34 passed in
  18.52s`, exit 0. It covers, in a `git init` project under `tmp_path`: `wants_proof_base` on
  dict flows (true for an outgoing `floor_gate`, true for `task_checks`, true through a `->DONE`
  wildcard for a state that can reach DONE and false for one that cannot, false for
  `command_gate`/`scope_gate`/`require_tasks_done` only, false for a gate on an edge INTO the
  state); `next_action` on the packaged `team-build` flow with `_load_flow` patched to add a
  `floor_gate` on `BUILDING->REVIEWING` stamps `proof_base` (a 40+ hex `tree` equal to the
  build baseline's, an aware `started_at`), a second call after an edit keeps the first value,
  and with no such gate nothing is stamped; the same on `goal-loop` with a `floor_gate` added to
  `DRAINING->DONE` (stamped on DRAINING, kept on a second call); outside a git repo `tree` is
  `None` and `started_at` parses; `complete_stage` BUILDING->REVIEWING keeps the base, the
  REVIEWING->BUILDING back-edge (a ready goal task) keeps it, RETRO->DONE drops it;
  `task_proven` is false before a record, true after a passing one, false after
  `retry_task` + `claim_task` (new `claimed_at`) and true again once the new claim is recorded,
  false for `floor: failed`, false for `checks: failed` or `error`, true for `checks: none` with
  floor `clean`/`off`/`n/a`, decided by the newest record, and not satisfied by another task's
  record; `record_task_proof` writes every field and refuses an unknown `checks` or `floor`.
  Mutation checks: with the DONE pop removed `test_the_transition_into_done_drops_the_base`
  fails; with the pop made unconditional `test_leaving_building_keeps_the_base` and
  `test_a_back_edge_keeps_the_base` fail.
- `python scripts/check_no_mirror_reads.py`: `check_no_mirror_reads: OK (8 allow-listed file(s)
  with markers)`, exit 0.
- Beyond the Done when: Test (`python -m pytest tests/ -q -x -p no:cacheprovider`) `2729 passed,
  14 skipped in 459.87s`, exit 0 (the skips are older tests; this ticket adds none). Lint chain,
  each link run: `black --check src/ tests/` (525 files unchanged), `mypy` (no issues in 294
  files), `check_file_size.py` (none new, none grown), `check_no_mirror_reads.py`,
  `gen_test_index.py --check`, `lint-imports` (1 kept, 0 broken), `bandit -q -r src/ -ll -x
  src/pathly_data/` (exit 0), `check_adapters.py`, `check_entry_points.py`: all exit 0. Smoke
  and `python -m build --wheel` exit 0.

**Decisions**

- `read_proof_base` and `task_proven` fail open: a DB error is logged (warning, with the
  traceback) and gives `None` and `False`. `None` makes a gate skip as "no proof base", `False`
  makes the checks run again, the safe direction. `windows_since` (ticket 04) raises instead;
  these two sit on the hot path of a gate that must never turn a DB hiccup into a 500.
- `record_task_proof` raises `ValueError` for a `checks` or `floor` outside the spec's sets
  (`CHECK_RESULTS`, `FLOOR_RESULTS`). A typo such as `"pass"` would otherwise record a proof
  that `task_proven` can never accept, and the checks would silently re-run forever.
- "Newest" `TASK_PROOF` means highest `seq` (event order), not `ts`, which has whole seconds.
- `claimed_at` is compared as the exact stored string (it is copied from the row, so a plain
  equality is exact). A task with no `claimed_at` matches a proof recorded with `claimed_at:
  None`.
- A back-edge test needs `goal_id`: `on_board_count` only fires when `complete_stage` is given
  one, and the pending task must carry the same `goal_id`.

**Shortcuts taken**

- `task_proven` reads the whole event log on every call (`eventlog.read_events`), so a join
  gate that checks N tasks reads it N times. Fine for tens of tasks; it stops being cheap for a
  run with thousands of events and hundreds of tasks. Worth upgrading (one read per gate, or a
  `TASK_PROOF`-only query in `db/queries`) if ticket 07's gate shows up in a profile.
- The stamp is only written by `next_action`, so a run already past its first
  `floor_gate`/`task_checks` state when the flow gains the gate (a resumed old run) gets its
  base from the next state that wants one, not from the start of the run.

**For later tickets**

- Tickets 05, 06, 07: use `_proof_record.read_proof_base(storage)` (a dict `{tree, started_at}`
  or `None`; `tree` may be `None` outside git, so the floor gate must skip then), and
  `record_task_proof(storage, task, run_id, checks, floor, warnings)` /
  `task_proven(storage, task)`; `task` is the comms row dict (`id`, `claimed_at`).
- Ticket 06 or 07, whichever first puts `floor_gate` or `task_checks` into a packaged flow: the
  `proof_base` paragraph in `src/pathly_orchestrator/CLAUDE.md` ends "No packaged flow declares
  a `floor_gate` or `task_checks` gate yet and nothing writes `TASK_PROOF`, so a real run stamps
  no base yet". Edit that sentence then. Also, once `floor_gate` is a flow gate, the `team-build`
  `BUILDING` stamp happens on first entry (BUILDING is where a team run starts), and `goal-loop`
  stamps on DRAINING via `DRAINING->DONE`.
- A test that patches `fsm_ops._load_flow` to a flow holding an unregistered gate type must not
  call `complete_stage` under the patch (`run_gates` raises `Unknown gate type`); use
  `monkeypatch.context()` around `next_action` only, as `test_leaving_building_keeps_the_base`
  does. Once 06 registers `floor_gate`, that restriction goes away.
