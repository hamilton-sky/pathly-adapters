# Stamp a run-wide proof base and record task proofs

Type: task
Status: open
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
