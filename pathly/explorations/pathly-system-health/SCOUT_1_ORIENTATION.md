# Scout 1 — Orientation (Structural Map)

Objective: Map file structure, layer connectivity, and dependency direction across:
- src/pathly_hooks/
- src/pathly_orchestrator/
- src/pathly_data/core/flows/
- src/install_cli/
- src/pathly_telemetry/
- src/pathly_data/core/skills/

Task:
1. List all files in each layer with 1-line descriptions
2. Identify key entry points (installer, hooks, orchestrator main)
3. Map dependency direction (e.g., installer → orchestrator → skills)
4. Identify files most critical to the three questions
5. Cross-reference with pathly/explorations/architecture-risk-assessment/TRACE.md for prior findings

Output: Structured map with file counts, layer roles, and risk hotspots.
