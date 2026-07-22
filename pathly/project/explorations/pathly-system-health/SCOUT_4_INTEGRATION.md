# Scout 4 — Flow & Integration (flow YAML, agent dispatch, skills)

Objective: Verify end-to-end agent routing and skill execution.

Files in scope:
- src/pathly_data/core/flows/ — flow YAML definitions (explore, team, debug, etc.)
- src/pathly_data/core/skills/ — skill prompts (explore.md, team.md, etc.)
- src/install_cli/ — adapter loading, flow materialization
- src/pathly_telemetry/ — HTTP telemetry, record_activity

Task:
1. Examine explore.flow.yaml: states, transitions, agent_map, feedback_routing
2. Trace agent spawn: how flow_config invokes agents, argument passing
3. Check skill loading: explore.md content, adapter-specific customization
4. Verify feedback file routing: how files trigger agent re-dispatch
5. Confirm autoFlow commits: when/how git commit happens
6. Test telemetry: record_activity call syntax, HTTP integration

Output: Integration flow diagram with agent entry/exit points and any wiring gaps.
