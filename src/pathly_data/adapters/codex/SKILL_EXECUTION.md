## Codex Execution Contract

This skill contains host-neutral Pathly role directions such as `Spawn builder`
or `Spawn reviewer`. Resolve those directions against capabilities available in
the active Codex session:

## Section 1 — Sub-agent spawning (primary path)

When `features.multi_agent = true` is enabled in `.codex/config.toml`:

1. Map the FSM `agent_hint.agent` value to `spawn_agent(agent_type=<name>, prompt=agent_hint.instructions)`.
   Role name mapping is direct — `agent_hint.agent` matches the `name` field in `.codex/agents/<name>.toml`.
2. Wait for the agent to finish: `wait_agent(thread_id)`.
3. Collect the result, then release: `close_agent(thread_id)`.
4. Call `complete_stage` only after the agent's result is collected and `close_agent` succeeds.

For read-only roles (explorer, scout, quick): `sandbox_mode = "restricted"` in their TOML
handles the access restriction — no special handling is needed in the skill itself.

## Section 2 — Inline fallback (when multi_agent is disabled)

When `features.multi_agent` is not enabled or `spawn_agent` is unavailable:

- `agent_hint.role` = `worker` → execute write-capable lifecycle work inline in the current agent.
- `agent_hint.role` = `explorer` → execute read-only research inline in the current agent.
- Never block or claim failure solely because a named Pathly role is not exposed as a callable
  Codex sub-agent. Follow `agent_hint.instructions` exactly and continue.

## Section 3 — FSM bridge

Use the packaged `pathly-fsm-call` HTTP bridge after each phase to communicate
with the live Pathly FSM server:

- `pathly-fsm-call next-action --flow <flow> --topic <feature> --project-root <abs path>`
- `pathly-fsm-call complete-stage --flow <flow> --topic <feature> --project-root <abs path>`
- `pathly-fsm-call record-activity --agent <role> --feature <feature> --summary <summary>`

Prefer the bridge over raw `curl` so Codex maintains consistent FSM and
telemetry behavior across builder, reviewer, tester, and support roles.

## Section 4 — Decision field

Every FSM response includes a `decision` field:

- `continue` — adapter may automate the next step without human involvement.
- `block` — an agent-resolvable feedback file is open. Surface to the next
  Pathly agent via the standard feedback resolution flow.
- `escalate` — human input is required (corrupt state, unknown feedback, or
  retry limit exceeded). Do not automate; surface to the user.
