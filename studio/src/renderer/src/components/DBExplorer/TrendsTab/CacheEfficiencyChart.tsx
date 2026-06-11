import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
} from 'recharts'
import styles from './TrendsTab.module.css'

interface CacheEfficiencyChartProps {
  events: DbEvent[]
}

interface CachePoint {
  index: number
  rate: number | null
}

function buildCachePoints(events: DbEvent[]): CachePoint[] {
  const agentDone = events
    .filter((e) => e.event_type === 'AGENT_DONE')
    .sort((a, b) => a.ts.localeCompare(b.ts))

  return agentDone.map((e, i) => {
    const cacheRead = Number(e.payload.cache_read_tokens ?? 0)
    const input = Number(e.payload.input_tokens ?? 0)
    const denom = cacheRead + input
    return {
      index: i,
      rate: denom === 0 ? null : (cacheRead / denom) * 100,
    }
  })
}

function computeOverallRate(events: DbEvent[]): number | null {
  const agentDone = events.filter((e) => e.event_type === 'AGENT_DONE')
  let totalCacheRead = 0
  let totalDenom = 0
  for (const e of agentDone) {
    const cacheRead = Number(e.payload.cache_read_tokens ?? 0)
    const input = Number(e.payload.input_tokens ?? 0)
    totalCacheRead += cacheRead
    totalDenom += cacheRead + input
  }
  return totalDenom === 0 ? null : (totalCacheRead / totalDenom) * 100
}

export function CacheEfficiencyChart({ events }: CacheEfficiencyChartProps): JSX.Element {
  const points = buildCachePoints(events)
  const overallRate = computeOverallRate(events)

  const cs = getComputedStyle(document.documentElement)
  const textMuted = cs.getPropertyValue('--text-muted').trim() || '#94a3b8'
  const bgSurface0 = cs.getPropertyValue('--bg-surface0').trim() || '#0d1117'
  const borderColor = cs.getPropertyValue('--border').trim() || '#283044'
  const textPrimary = cs.getPropertyValue('--text-primary').trim() || '#e2e8f0'
  const fontMono = cs.getPropertyValue('--font-family-mono').trim() || 'monospace'
  const accentColor = 'var(--accent)'

  const hasAnyData = points.some((p) => p.rate !== null)
  const summaryLabel =
    overallRate === null ? 'No cache data' : `Overall: ${overallRate.toFixed(1)}%`

  return (
    <div className={styles.cacheChartWrapper}>
      <p className={styles.cacheSummary}>{summaryLabel}</p>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={points} margin={{ left: 0, right: 16, top: 4, bottom: 0 }}>
          <XAxis
            dataKey="index"
            tick={{ fontSize: 10, fill: textMuted, fontFamily: fontMono }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            domain={[0, 100]}
            tickFormatter={(v: number) => `${v}%`}
            tick={{ fontSize: 10, fill: textMuted, fontFamily: fontMono }}
            tickLine={false}
            axisLine={false}
            width={48}
          />
          <Tooltip
            formatter={(value) => [`${Number(value ?? 0).toFixed(1)}%`, 'Cache hit rate']}
            labelFormatter={(label) => `Run #${label}`}
            contentStyle={{
              background: bgSurface0,
              border: `1px solid ${borderColor}`,
              color: textPrimary,
              fontSize: 12,
            }}
          />
          <Line
            type="monotone"
            dataKey="rate"
            stroke={accentColor}
            dot={false}
            connectNulls={false}
          />
        </LineChart>
      </ResponsiveContainer>
      {!hasAnyData && (
        <p className={styles.empty}>No cache data</p>
      )}
    </div>
  )
}
