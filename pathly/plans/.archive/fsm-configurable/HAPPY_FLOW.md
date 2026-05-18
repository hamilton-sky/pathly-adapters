# fsm-configurable — Happy Flow

This narrative describes the golden path once all three conversations are complete.

---

## Scenario: user starts a new debug session

1. User invokes `/debug symptom:login-timeout rigor:standard`.
2. `debug.md` parses the symptom name (`login-timeout`), confirms rigor, then reaches the `## Spawn orchestrator` block.
3. debug.md spawns the orchestrator agent with:
   - `flow_config: src/pathly_data/core/flows/debug.flow.yaml`
   - `topic: login-timeout`
   - `rigor: standard`
4. Orchestrator reads `src/pathly_data/core/flows/debug.flow.yaml`. It learns:
   - `storage_path: debugs/login-timeout/`
   - states: INVESTIGATING → REPRODUCING → ROOT_CAUSE_FOUND → FIXING → VERIFYING → DONE
   - agent_map: INVESTIGATING → scout, FIXING → builder, VERIFYING → tester
   - feedback_routing: TEST_FAILURES → builder, HUMAN_QUESTIONS → human
5. Orchestrator creates `debugs/login-timeout/STATE.json` (state: INVESTIGATING) and `debugs/login-timeout/EVENTS.jsonl`.
6. Orchestrator transitions through states, spawning the agent named in `agent_map` at each state.
7. When VERIFYING passes, orchestrator writes final state DONE to STATE.json and stops.

The user sees the same structured tracking they get from a team pipeline run — STATE.json, EVENTS.jsonl — but in `debugs/login-timeout/` rather than `plans/`.

---

## Scenario: user starts a feature build (team pipeline)

1. User invokes `/team feature:auth-refresh rigor:standard`.
2. `team.md` parses inputs, reaches `## Spawn orchestrator`, passes:
   - `flow_config: src/pathly_data/core/flows/team.flow.yaml`
   - `topic: auth-refresh`
3. Orchestrator reads `src/pathly_data/core/flows/team.flow.yaml`:
   - `storage_path: plans/auth-refresh/`
   - states: IDLE → STORMING → PLANNING → BUILDING → REVIEWING → TESTING → RETRO → DONE
   - agent_map: PLANNING → team/plan, BUILDING → team/build, etc.
4. Behaviour is identical to the pre-refactor team pipeline from the user's perspective — but orchestrator.md no longer contains any team-specific literals.

---

## Scenario: contributor adds a new flow (e.g., `audit`)

1. Contributor creates `src/pathly_data/core/flows/audit.flow.yaml` with states, transitions, agent_map, storage_path, feedback_routing.
2. Contributor creates or updates `src/pathly_data/core/skills/audit.md` with a spawn block passing `flow_config: src/pathly_data/core/flows/audit.flow.yaml`.
3. No changes to orchestrator.md — it handles the new flow generically.

---

## What success looks like

- `orchestrator.md` has no team-specific state names in its logic.
- Three flow YAML files exist under `core/flows/`, one per flow.
- All three skill launchers (team, debug, explore) spawn orchestrator with a `flow_config` path.
- Debug and explore runs produce `STATE.json` and `EVENTS.jsonl` in their respective storage directories.
- Adding a fourth flow requires zero changes to orchestrator.md.
