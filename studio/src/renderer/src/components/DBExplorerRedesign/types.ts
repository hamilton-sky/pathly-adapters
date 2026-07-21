export type PipelineState =
  | 'PLANNING'
  | 'BUILDING'
  | 'REVIEWING'
  | 'TESTING'
  | 'RETRO'
  | 'DONE'

export interface DotSegment {
  state: PipelineState
  flex?: number
}

export interface FeatureData {
  name: string
  state: PipelineState
  events: number
  inv: number
  tokens: string
  cost: string
  /** Numeric cost, used for the circular-metric aggregations. */
  costN: number
  ts: string
  dots: DotSegment[]
}

export interface TransitionData {
  state: PipelineState
  time: string
  duration: string
  /** 0–1 fraction of the longest stage, drives the timeline bar width. */
  w: number
}

export interface EventData {
  time: string
  type: string
  detail: string
  state: PipelineState
}

export interface AgentData {
  role: 'builder' | 'reviewer' | 'tester'
  conv: string
  state: PipelineState
  cost: number
}

export interface TraceData {
  name: string
  agent: string
  model: string
  tokIn: number
  tokOut: number
  cost: number
  /** Duration in ms. */
  dur: number
  result: string
}

/** A raw pipeline event, expandable to its JSON payload in the Events tab. */
export interface EventRow {
  seq: number
  type: string
  ts: string
  summary: string
  payload: Record<string, unknown>
}

/** One day of the Trends daily-cost chart (estimated + reported dollars). */
export interface DailyCostPoint {
  /** MM-DD or ISO date. */
  date: string
  estimated: number
  reported: number
}

/** Roll-up scope tier row. */
export interface RollupTier {
  tier: 'feature' | 'project' | 'global'
  agents: number
  cost: string
  tokens: string
}

export interface RollupCard {
  title: string
  sub: string
  totals: { n: string; l: string }[]
  tiers: RollupTier[]
  projects?: { name: string; cost: string; agents: string }[] | null
}

/** Grid / stack (list) / roll-up view of the feature collection. */
export type ViewMode = 'grid' | 'stack' | 'rollup'

export interface CostPoint {
  /** ISO-ish day or MM/DD label. */
  day: string
  cost: number
}

/** Which dataset the circular metric renders. */
export type MetricKey = 'state' | 'agent' | 'tokens' | 'status'

/** Chart + metric arrangement. */
export type LayoutMode = 'A' | 'B' | 'C'

export interface TopStat {
  k: string
  v: string
  /** true → render in the green cost colour. */
  cost?: boolean
}

/** Per-state hex map — the FSM domain colours. */
export const STATE_COLORS: Record<PipelineState, string> = {
  PLANNING: 'var(--state-planning)',
  BUILDING: 'var(--state-building)',
  REVIEWING: 'var(--state-reviewing)',
  TESTING: 'var(--state-testing)',
  RETRO: 'var(--state-retro)',
  DONE: 'var(--state-done)',
}
