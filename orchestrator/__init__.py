"""
Pathly orchestrator — FSM state and event log for team-flow pipelines.

The orchestrator is the LLM (main assistant) running the team-flow skill.
These Python modules serve two purposes:
  1. Schema reference — the LLM reads them to know what JSON to write
  2. Bash-callable CLI — `python -m orchestrator.eventlog <cmd>` for summaries
"""
