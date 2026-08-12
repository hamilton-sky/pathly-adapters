import type { FeatureData, MetricKey, PipelineState } from './types'

/** Summed token breakdown for the donut's "tokens" mode (from trends buckets). */
export interface TokenSplit {
  input: number
  cacheRead: number
  output: number
}

/** Per-role cost/token aggregate for the donut's "agent" mode. */
export interface AgentRoleAgg {
  role: string
  cost: number
  tokens: number
}

/** Everything the donut can aggregate. tokenSplit/agentRoles are null until loaded. */
export interface MetricInputs {
  features: FeatureData[]
  tokenSplit: TokenSplit | null
  agentRoles: AgentRoleAgg[] | null
}

interface MetricSegment {
  label: string
  /** Theme-token color string, e.g. "var(--state-done)". */
  color: string
  value: number
}

export interface MetricResult {
  title: string
  segs: MetricSegment[]
  total: number
  /** Big number shown in the donut hole. */
  center: string
  centerLabel: string
  /** Formats a segment value for the legend. */
  fmt: (v: number) => string
  /** True when the source data for this metric has not loaded yet. */
  pending?: boolean
}

const STATE_TOKEN: Record<PipelineState, string> = {
  PLANNING: 'var(--state-planning)',
  BUILDING: 'var(--state-building)',
  REVIEWING: 'var(--state-reviewing)',
  TESTING: 'var(--state-testing)',
  RETRO: 'var(--state-retro)',
  DONE: 'var(--state-done)',
}

const STATE_ORDER: PipelineState[] = ['PLANNING', 'BUILDING', 'REVIEWING', 'TESTING', 'RETRO', 'DONE']

function roleToken(role: string): string {
  const r = role.toLowerCase()
  if (r.includes('build')) return 'var(--state-building)'
  if (r.includes('review')) return 'var(--state-reviewing)'
  if (r.includes('test')) return 'var(--state-testing)'
  if (r.includes('plan') || r.includes('architect')) return 'var(--state-planning)'
  if (r.includes('design')) return 'var(--runtime)'
  return 'var(--accent)'
}

const sum = (segs: MetricSegment[]): number => segs.reduce((a, s) => a + s.value, 0)
const money = (v: number): string => `$${v.toFixed(2)}`
const titleCase = (s: string): string => s.charAt(0).toUpperCase() + s.slice(1).toLowerCase()

function fmtTokens(v: number): string {
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`
  if (v >= 1e3) return `${Math.round(v / 1e3)}K`
  return String(v)
}

/**
 * Aggregates live panel data into the segments the CircularMetric donut renders.
 * Colours are theme tokens (var(--*)) so the donut inherits the active theme.
 */
export function computeMetric(key: MetricKey, inputs: MetricInputs): MetricResult {
  const { features, tokenSplit, agentRoles } = inputs

  if (key === 'state') {
    const groups: Partial<Record<PipelineState, number>> = {}
    features.forEach((f) => { groups[f.state] = (groups[f.state] ?? 0) + f.costN })
    const segs = STATE_ORDER
      .filter((s) => (groups[s] ?? 0) > 0)
      .map((s) => ({ label: titleCase(s), color: STATE_TOKEN[s], value: groups[s] as number }))
    const total = sum(segs)
    return { title: 'Cost by pipeline state', segs, total, center: money(total), centerLabel: 'total cost', fmt: money }
  }

  if (key === 'agent') {
    if (!agentRoles) {
      return { title: 'Agent cost share', segs: [], total: 0, center: '—', centerLabel: 'loading', fmt: money, pending: true }
    }
    const segs = agentRoles
      .filter((a) => a.cost > 0)
      .map((a) => ({ label: titleCase(a.role), color: roleToken(a.role), value: a.cost }))
    const total = sum(segs)
    return { title: 'Agent cost share', segs, total, center: money(total), centerLabel: `${segs.length} roles`, fmt: money }
  }

  if (key === 'tokens') {
    if (!tokenSplit) {
      return { title: 'Token usage split', segs: [], total: 0, center: '—', centerLabel: 'loading', fmt: fmtTokens, pending: true }
    }
    const segs: MetricSegment[] = [
      { label: 'Input', color: 'var(--accent)', value: tokenSplit.input },
      { label: 'Cache read', color: 'var(--green)', value: tokenSplit.cacheRead },
      { label: 'Output', color: 'var(--runtime)', value: tokenSplit.output },
    ].filter((s) => s.value > 0)
    const total = sum(segs)
    return { title: 'Token usage split', segs, total, center: fmtTokens(total), centerLabel: 'total tokens', fmt: fmtTokens }
  }

  // status — count of features per state
  const groups: Partial<Record<PipelineState, number>> = {}
  features.forEach((f) => { groups[f.state] = (groups[f.state] ?? 0) + 1 })
  const segs = STATE_ORDER
    .filter((s) => (groups[s] ?? 0) > 0)
    .map((s) => ({ label: titleCase(s), color: STATE_TOKEN[s], value: groups[s] as number }))
  const total = sum(segs)
  return { title: 'Feature status', segs, total, center: String(total), centerLabel: 'features', fmt: (v) => String(v) }
}

/** Builds the conic-gradient string + legend rows from a metric result. */
function toDonut(m: MetricResult): {
  gradient: string
  legend: { label: string; color: string; value: string; pct: string }[]
} {
  const total = m.total || 1
  let acc = 0
  const stops = m.segs.map((s) => {
    const from = (acc / total) * 100
    acc += s.value
    const to = (acc / total) * 100
    return `${s.color} ${from}% ${to}%`
  })
  const gradient = m.segs.length ? `conic-gradient(${stops.join(', ')})` : 'var(--bg-surface0)'
  const legend = m.segs.map((s) => ({
    label: s.label,
    color: s.color,
    value: m.fmt(s.value),
    pct: `${Math.round((s.value / total) * 100)}%`,
  }))
  return { gradient, legend }
}
