import { useEffect, useState } from 'react'
import { apiGetAgents } from '../../../../store/commsApi'

// The pipeline agent roles the model policy can target, sourced from the registry (core/agents/
// → agent_definitions via GET /db/agents) so a newly-created agent appears automatically instead
// of being hard-coded. `human` is dropped — it's the human-in-the-loop placeholder and never
// spawns a CLI. Falls back to this built-in list until the server responds (or on an older server
// without the route), so the section is never empty.
const FALLBACK_ROLES = [
  'architect', 'planner', 'po', 'builder', 'designer', 'reviewer', 'tester',
  'scout', 'explorer', 'web-researcher', 'evaluator', 'director', 'quick', 'orchestrator',
]

export function useAgents(): string[] {
  const [roles, setRoles] = useState<string[]>(FALLBACK_ROLES)

  useEffect(() => {
    let alive = true
    void apiGetAgents().then((agents) => {
      if (!alive) return
      const live = agents.map((a) => a.role).filter((r) => r && r !== 'human')
      if (live.length) setRoles(live)
    })
    return () => {
      alive = false
    }
  }, [])

  return roles
}
