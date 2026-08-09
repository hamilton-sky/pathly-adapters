import { ModelsSettings } from '../ModelsSettings/ModelsSettings'
import { LoggingSettings } from '../LoggingSettings/LoggingSettings'

// Spawn-policy control plane (SPEC: pathly/features/spawn-policy/): one place to set which model
// each agent uses and where agents narrate. Both sections write DB-backed config read by BOTH the
// renderer gate and the Python resolver, so every spawn — runner, board, editor one-shot — obeys
// the same policy. Two sections only (models + logging); roles and places are the same axis.
export function AgentsSettings(): JSX.Element {
  return (
    <>
      <ModelsSettings />
      <LoggingSettings />
    </>
  )
}
