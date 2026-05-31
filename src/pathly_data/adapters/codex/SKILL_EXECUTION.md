## Codex Execution Contract

This skill contains host-neutral Pathly role directions such as `Spawn builder`
or `Spawn reviewer`. Resolve those directions against capabilities available in
the active Codex session:

- If Codex exposes the named Pathly role as callable, invoke it with the
  requested phase and prompt.
- If an FSM response includes `codex_subagent`, use it as the Codex fallback
  routing contract. `codex_subagent.codex_role` is the callable Codex role
  (`worker` or `explorer`), and `codex_subagent.instructions` is the complete
  delegated prompt containing the Pathly role, phase, artifacts, and limits.
- Use Codex sub-agent delegation when the user has requested or approved Pathly
  subagents and the active Codex tool policy permits it. Route read-only
  research roles (`explorer`, `scout`, `web-researcher`, `quick`) to Codex
  `explorer`; route write-capable lifecycle roles (`planner`, `architect`,
  `po`, `designer`, `builder`, `reviewer`, `tester`, `orchestrator`) to Codex
  `worker`.
- If delegation is not available or not permitted, execute the Pathly role work
  in the current Codex agent while following the returned instructions exactly.
- Never block or claim failure solely because a named Pathly role is not
  exposed as a callable Codex sub-agent.
- Use the packaged `pathly-fsm-call` HTTP bridge after each phase to talk to
  the live Pathly FSM server:
  - `pathly-fsm-call next-action --flow <flow> --topic <feature> --project-root <abs path>`
  - `pathly-fsm-call complete-stage --flow <flow> --topic <feature> --project-root <abs path>`
  - `pathly-fsm-call record-activity --agent <role> --feature <feature> --summary <summary>`
- Prefer the bridge over raw `curl` so Codex can keep the same FSM/telemetry
  behavior across builder, reviewer, tester, and support roles.

Installed `agents/*.toml` files preserve Pathly role contracts for Codex
surfaces that load custom agents; they are not by themselves proof that the
active session can invoke those role names.
