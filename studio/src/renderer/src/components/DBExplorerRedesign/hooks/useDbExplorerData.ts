import { useState, useEffect, useCallback } from 'react'
import { useProjectStore } from '../../../store/projectStore'
import type { FeatureData, PipelineState, TopStat } from '../types'
import type { TokenSplit, AgentRoleAgg } from '../metricUtils'

type ScopeMode = 'project' | 'global'
type RangeDays = 7 | 14 | 30

interface ChartSummary {
  /** Contiguous daily cost, oldest → newest, gap-filled across the range. */
  series: number[]
  startDate: Date
  /** Index of the peak bar (−1 when the series is all zero). */
  peakIndex: number
  total: string
  avgPerActiveDay: string
  peak: string
  peakDay: string
  spanCount: number
}

export interface DbExplorerData {
  features: FeatureData[]
  topStats: TopStat[]
  chart: ChartSummary
  tokenSplit: TokenSplit | null
  agentRoles: AgentRoleAgg[] | null
  loading: boolean
  costLoading: boolean
  scope: ScopeMode
  setScope: (s: ScopeMode) => void
  range: RangeDays
  setRange: (r: RangeDays) => void
  refresh: () => void
}

function mapState(s: string): PipelineState {
  const upper = s.toUpperCase()
  if (upper === 'DONE') return 'DONE'
  if (upper === 'RETRO') return 'RETRO'
  if (['TESTING', 'TEST'].includes(upper)) return 'TESTING'
  if (['REVIEWING', 'REVIEW'].includes(upper)) return 'REVIEWING'
  if (['BUILDING', 'BUILD', 'DESIGN', 'DESIGNING'].includes(upper)) return 'BUILDING'
  return 'PLANNING'
}

function dbFeatureToFeatureData(f: DbFeature): FeatureData {
  const state = mapState(f.state)
  return {
    name: f.feature,
    state,
    events: f.events,
    inv: f.invocations,
    tokens: f.total_tokens.toLocaleString(),
    cost: `$${f.cost_usd.toFixed(2)}`,
    costN: f.cost_usd,
    ts: f.updated_at ? f.updated_at.slice(11, 19) : '',
    dots: [{ state }],
  }
}

function statsToTopStats(s: DbStats | null): TopStat[] {
  if (!s) {
    return [
      { k: 'Features', v: '0' }, { k: 'Events', v: '0' }, { k: 'Invocations', v: '0' },
      { k: 'Tokens', v: '0' }, { k: 'Cost', v: '$0.00', cost: true },
    ]
  }
  return [
    { k: 'Features', v: String(s.features) },
    { k: 'Events', v: s.events.toLocaleString() },
    { k: 'Invocations', v: s.invocations.toLocaleString() },
    { k: 'Tokens', v: s.total_tokens.toLocaleString() },
    { k: 'Cost', v: `$${s.total_cost_usd.toFixed(2)}`, cost: true },
  ]
}

const pad2 = (n: number): string => String(n).padStart(2, '0')
const isoDay = (d: Date): string => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
const fmtDayLabel = (d: Date): string => `${pad2(d.getMonth() + 1)}/${pad2(d.getDate())}`
const fmtMoney = (v: number): string => `$${v.toFixed(2)}`

function buildChart(buckets: DailyTrendBucket[], range: number, today: Date): ChartSummary {
  const byDate = new Map<string, number>()
  buckets.forEach((b) => byDate.set(b.bucket, (byDate.get(b.bucket) ?? 0) + b.cost_usd_reported))
  const start = new Date(today)
  start.setDate(today.getDate() - (range - 1))
  const series: number[] = []
  for (let i = 0; i < range; i++) {
    const d = new Date(start)
    d.setDate(start.getDate() + i)
    series.push(byDate.get(isoDay(d)) ?? 0)
  }
  const total = series.reduce((a, v) => a + v, 0)
  const activeDays = series.filter((v) => v > 0).length || 1
  const peakVal = series.reduce((m, v) => Math.max(m, v), 0)
  const peakIndex = peakVal > 0 ? series.indexOf(peakVal) : -1
  let peakDay = '—'
  if (peakIndex >= 0) {
    const d = new Date(start)
    d.setDate(start.getDate() + peakIndex)
    peakDay = fmtDayLabel(d)
  }
  return {
    series,
    startDate: start,
    peakIndex,
    total: fmtMoney(total),
    avgPerActiveDay: fmtMoney(total / activeDays),
    peak: fmtMoney(peakVal),
    peakDay,
    spanCount: buckets.reduce((a, b) => a + b.count, 0),
  }
}

function buildTokenSplit(buckets: DailyTrendBucket[]): TokenSplit {
  let input = 0
  let cacheRead = 0
  let output = 0
  buckets.forEach((b) => {
    input += b.input_tokens ?? 0
    cacheRead += b.cache_read_tokens ?? 0
    output += Math.max(0, (b.total_tokens ?? 0) - (b.input_tokens ?? 0))
  })
  return { input, cacheRead, output }
}

async function queryAgentRoles(projectRoot: string | null): Promise<AgentRoleAgg[]> {
  if (!projectRoot) return []
  const esc = projectRoot.replace(/'/g, "''")
  const sql =
    'SELECT agent_role AS role, SUM(cost_usd) AS cost, ' +
    'SUM(COALESCE(tokens_in,0)+COALESCE(tokens_out,0)) AS tokens ' +
    `FROM agent_invocations WHERE project_root = '${esc}' ` +
    "AND agent_role IS NOT NULL AND agent_role != '' GROUP BY agent_role ORDER BY cost DESC"
  try {
    const res = await window.pathly.db.query(sql)
    return (res?.rows ?? []).map((r) => ({
      role: String(r.role ?? ''),
      cost: Number(r.cost ?? 0),
      tokens: Number(r.tokens ?? 0),
    }))
  } catch {
    return []
  }
}

/** Loads all live data the redesigned DB Explorer panel renders. */
export function useDbExplorerData(): DbExplorerData {
  const projectPath = useProjectStore((s) => s.projectPath)
  const [features, setFeatures] = useState<FeatureData[]>([])
  const [topStats, setTopStats] = useState<TopStat[]>(statsToTopStats(null))
  const [chart, setChart] = useState<ChartSummary>(() => buildChart([], 30, new Date()))
  const [tokenSplit, setTokenSplit] = useState<TokenSplit | null>(null)
  const [agentRoles, setAgentRoles] = useState<AgentRoleAgg[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [costLoading, setCostLoading] = useState(true)
  const [scope, setScope] = useState<ScopeMode>('project')
  const [range, setRange] = useState<RangeDays>(30)

  const load = useCallback(async () => {
    setLoading(true)
    setAgentRoles(null)
    try {
      const [rawFeatures, rawStats] = await Promise.all([
        window.pathly.db.features(projectPath || undefined),
        window.pathly.db.stats(projectPath || undefined),
      ])
      setFeatures(rawFeatures.map(dbFeatureToFeatureData))
      setTopStats(statsToTopStats(rawStats))
      const pr = rawFeatures[0]?.project_root ?? projectPath ?? null
      queryAgentRoles(pr).then(setAgentRoles)
    } catch {
      setFeatures([])
      setTopStats(statsToTopStats(null))
      setAgentRoles([])
    } finally {
      setLoading(false)
    }
  }, [projectPath])

  const loadTrends = useCallback(async () => {
    setCostLoading(true)
    try {
      const root = scope === 'global' ? undefined : projectPath || undefined
      const raw = await window.pathly.db.trends('', range, root)
      const buckets = raw?.trends ?? []
      setChart(buildChart(buckets, range, new Date()))
      setTokenSplit(buildTokenSplit(buckets))
    } catch {
      setChart(buildChart([], range, new Date()))
      setTokenSplit(null)
    } finally {
      setCostLoading(false)
    }
  }, [projectPath, scope, range])

  useEffect(() => { load() }, [load])
  useEffect(() => { loadTrends() }, [loadTrends])

  const refresh = useCallback(() => { load(); loadTrends() }, [load, loadTrends])

  return {
    features, topStats, chart, tokenSplit, agentRoles,
    loading, costLoading, scope, setScope, range, setRange, refresh,
  }
}
