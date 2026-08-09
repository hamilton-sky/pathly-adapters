import { useEffect, useState } from 'react'
import {
  apiClearModelPolicy,
  apiGetModelPolicy,
  apiSetModelPolicy,
  type ModelPolicy,
} from '../../../../store/commsApi'

// Loads + persists the per-agent model policy — the single DB-backed source of truth for which
// company + model each spawn uses (read by BOTH the renderer gate and the Python resolver). Seeds
// from GET /comms/model-policy on mount; every setter updates local state optimistically and
// writes back via POST. Falls back to an empty policy (everything on the engine default) until the
// server responds, so the UI never blocks.
export function useModelPolicy(): {
  policy: ModelPolicy
  setDefault: (adapter: string, model: string) => void
  clearDefault: () => void
  setRole: (role: string, adapter: string, model: string) => void
  clearRole: (role: string) => void
} {
  const [policy, setPolicy] = useState<ModelPolicy>({ default: null, roles: {} })

  useEffect(() => {
    let alive = true
    void apiGetModelPolicy().then((p) => {
      if (alive && p) setPolicy(p)
    })
    return () => {
      alive = false
    }
  }, [])

  function setDefault(adapter: string, model: string): void {
    setPolicy((p) => ({ ...p, default: { adapter, model } }))
    void apiSetModelPolicy(null, adapter, model)
  }

  function clearDefault(): void {
    setPolicy((p) => ({ ...p, default: null }))
    void apiClearModelPolicy(null)
  }

  function setRole(role: string, adapter: string, model: string): void {
    setPolicy((p) => ({ ...p, roles: { ...p.roles, [role]: { adapter, model } } }))
    void apiSetModelPolicy(role, adapter, model)
  }

  function clearRole(role: string): void {
    setPolicy((p) => {
      const roles = { ...p.roles }
      delete roles[role]
      return { ...p, roles }
    })
    void apiClearModelPolicy(role)
  }

  return { policy, setDefault, clearDefault, setRole, clearRole }
}
