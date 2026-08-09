import { ModelsSettings } from '../ModelsSettings/ModelsSettings'

// Per-agent spawn configuration ("Agents" settings group) — currently which model each agent
// spawns with (ModelsSettings). Logging is deliberately NOT here: every agent's run logs, cost,
// and observability live in the Pipeline section (the unified-control-plane sink — always on, not
// a setting), and board posting is context governance the governance agents own, not something a
// user configures. Settings is for "the rest" (config); the Pipeline is for observe/control.
export function AgentsSettings(): JSX.Element {
  return <ModelsSettings />
}
