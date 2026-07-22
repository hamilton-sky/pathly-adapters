# Scout 3 — FSM Engine (orchestrator, state, events)

Objective: Verify FSM correctness: state transitions, event logging, agent dispatch.

Files in scope:
- src/pathly_orchestrator/ — FSM engine, state management
- src/pathly_data/core/flows/ — flow YAML syntax and structure

Task:
1. Trace orchestrator startup: config load, state recovery from disk
2. Examine state machine loop: read STATE.json, apply event, emit next action
3. Check event logging: EVENTS.jsonl format, append correctness
4. Verify transition rules evaluation: on_artifact logic, default fallback
5. Confirm feedback routing after each event
6. Identify any threading/concurrency issues

Output: FSM trace with test points and any correctness issues found.
