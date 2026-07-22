# Exploration — production-readiness-plan

## Question

What does the `single` executor's goal → DAG → drain loop actually execute, stage by stage,
and what artifact gates or DB state changes does each FSM transition check — giving us the
complete picture needed to write the T1 golden-path CI smoke test?

Specifically:
1. How does `start_goal_run` (single executor) reach `board_run.start_board_run` and then the
   `supervisor` loop?
2. What does `drain-dag` skill do inside a single-executor run — task claim → execute → complete
   cycle in the DB?
3. What does the `team-build` FSM flow look like stage by stage, and what artifact gate or
   condition does each transition check?
4. Where does `_run_stage_via_terminal` fit — can it be stubbed cleanly the same way
   `test_runner_fsm_integration.py` stubs it without losing meaningful coverage?
5. What is the minimum fixture setup a `test_golden_path.py` needs so that a single-executor run
   can reach DONE in an isolated tmp_path without spawning a real CLI?

## Scope

- `supervisor/goal_executor.py` — single executor dispatch path
- `supervisor/board_run.py` — `start_board_run`, board-lock + skill compose + spawn helper
- `supervisor/goal_decomposer.py` — how a goal seeds its task DAG
- `supervisor/orchestrator.py` — `_loop`, `_resolve_stage_supervised`
- `supervisor/scheduler.py` — DAG frontier loop (`scheduler_loop`)
- `src/pathly_data/core/flows/team-build.flow.yaml` — the flow the `team` executor and `single`
  executor both use; stage list + transition rules
- `src/pathly_data/core/skills/development/drain-dag.md` — what the drain-dag skill instructs
  the agent to do
- `tests/test_runner_fsm_integration.py` — existing integration tests (what's already covered)

## Out of scope

- Studio/Electron spawn layer (already traced in SPEC §5 telemetry section)
- Telemetry paths (B1/B2/B3 fully traced in SPEC §5)
- The comms board endpoint internals beyond what the drain-dag loop calls
- The `loop` and `team` executor strategies (only `single` is in scope for T1)
- Real CLI invocation (T1 is a pytest smoke test — stubs are expected)

## Success criterion

We can answer: "Here is the minimal `test_golden_path.py` skeleton — the fixture setup, the
three stubs (next_action display, complete_stage real, _run_stage_via_terminal no-op), the
drain-dag task-claim sequence, and the final assertion that the feature reaches DONE — such
that T1 can be written as a single pytest file that passes in CI without a live Claude CLI."
