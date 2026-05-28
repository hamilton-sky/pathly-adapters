---
description: /pathly team, full pipeline, run team, team
name: team
---

## Codex Execution Contract

This skill contains host-neutral Pathly role directions such as `Spawn builder`
or `Spawn reviewer`. Resolve those directions against capabilities available in
the active Codex session.

Installed `agents/*.toml` files preserve Pathly role contracts for Codex
surfaces that load custom agents; they are not by themselves proof that the
active session can invoke those role names.

Do not keep a static menu in this skill. Always render the menu payload returned
by the FSM-backed Python surface.

# team

Unified entry point for the Pathly team pipeline.
HTTP/FSM engine first (auto-starts the Python server via `fsm-call`); falls back to
the LLM orchestrator if the server cannot start.

Run for `$ARGUMENTS`.

## Behavior

- Parse the feature, rigor, and mode flags from `$ARGUMENTS`.
- Detect or confirm the active feature if needed.
- Ask the FSM for `next_action`.
- Render the returned `menu` payload instead of duplicating menu prose here.
- Execute the returned agent instructions exactly.
- If the FSM returns blocked feedback, surface the feedback and route to the
  correct resolver.
