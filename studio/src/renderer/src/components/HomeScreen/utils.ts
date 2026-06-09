import type { PlanRow } from './types'

export function timeAgo(ts: number): string {
  const diffMs = Date.now() - ts
  const diffSec = Math.floor(diffMs / 1000)
  if (diffSec < 60) return `${diffSec}s ago`
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin} min ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr} hr ago`
  return `${Math.floor(diffHr / 24)}d ago`
}

export function getCardStatus(plans: PlanRow[]): 'blocked' | 'active' | 'idle' {
  if (plans.some((p) => p.state.toUpperCase() === 'BLOCKED')) return 'blocked'
  if (plans.some((p) => { const s = p.state.toUpperCase(); return s && s !== 'DONE' && s !== 'IDLE' })) return 'active'
  return 'idle'
}
