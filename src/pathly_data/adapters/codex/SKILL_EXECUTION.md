## Codex Execution Contract

This skill contains host-neutral Pathly role directions such as `Spawn builder`
or `Spawn reviewer`. Resolve those directions against capabilities available in
the active Codex session:

- If Codex exposes the named Pathly role as callable, invoke it with the
  requested phase and prompt.
- Otherwise, execute lifecycle role work (`planner`, `architect`, `builder`,
  `reviewer`, `tester`, `orchestrator`, `po`) in the current Codex agent while
  following the role and phase instructions in this skill.
- Use Codex sub-agent delegation only when the user has requested delegation
  and the active Codex tool policy permits it. When permitted, map
  implementation work to a write-capable worker and read-only investigation
  to an explorer, including the Pathly role, phase, and constraints in the
  delegated prompt.
- Never block or claim failure solely because a named Pathly role is not
  exposed as a callable Codex sub-agent.

Installed `agents/*.toml` files preserve Pathly role contracts for Codex
surfaces that load custom agents; they are not by themselves proof that the
active session can invoke those role names.
