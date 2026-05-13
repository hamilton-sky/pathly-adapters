# Exploration — pathly-system-health

## Question
Does the Pathly system work end-to-end? Specifically:
1. Is the overall architecture coherent and correctly wired?
2. Does the FSM (orchestrator + flow YAML) work correctly — state transitions, event logging, agent dispatch?
3. Are the hooks (classify_feedback, inject_feedback_ttl) reliable, and how can they be improved?

## Scope
- `src/pathly_hooks/` — hook scripts, env var handling, exit code behavior
- `src/pathly_orchestrator/` — FSM engine, eventlog, state management
- `src/pathly_data/core/flows/` — flow YAML definitions
- `src/install_cli/` — installer, materialize, hook registration
- `src/pathly_telemetry/` — MCP telemetry server
- `src/pathly_data/core/skills/` — skill definitions (especially explore.md, the recently updated one)
- Existing risk findings in `pathly/explorations/architecture-risk-assessment/TRACE.md`

## Out of scope
- Adapter-specific YAML files under `src/pathly_data/adapters/`
- Pipeline walkthrough docs in `pathly/pipeline-walkthrough/`
- Archived plan folders in `pathly/plans/.archive/`

## Success criterion
We can answer:
- Yes/No: does the FSM drive a full explore flow without breaking?
- Yes/No: do the hooks fail gracefully and correctly in all documented scenarios?
- Concrete list: 2–5 actionable hook improvements with file:line pointers
