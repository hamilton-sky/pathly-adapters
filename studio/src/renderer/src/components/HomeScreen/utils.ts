import type { PlanRow } from './types'

export function getCardStatus(plans: PlanRow[]): 'blocked' | 'active' | 'idle' {
  if (plans.some((p) => p.state.toUpperCase() === 'BLOCKED')) return 'blocked'
  if (plans.some((p) => { const s = p.state.toUpperCase(); return s && s !== 'DONE' && s !== 'IDLE' })) return 'active'
  return 'idle'
}
