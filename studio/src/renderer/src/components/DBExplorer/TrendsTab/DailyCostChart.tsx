import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
} from 'recharts'
import type { DailyCostPoint } from './useTrends'
import styles from './TrendsTab.module.css'

interface DailyCostChartProps {
  data: DailyCostPoint[]
}

function formatDate(dateStr: string): string {
  const [, mm, dd] = dateStr.split('-')
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  return `${months[parseInt(mm, 10) - 1]} ${dd}`
}

function formatDollar(v: number): string {
  return `$${v.toFixed(4)}`
}

export function DailyCostChart({ data }: DailyCostChartProps): JSX.Element {
  if (data.length === 0) {
    return <p className={styles.empty}>No cost data recorded yet</p>
  }

  const cs = getComputedStyle(document.documentElement)
  const textMuted = cs.getPropertyValue('--text-muted').trim() || '#94a3b8'
  const bgSurface0 = cs.getPropertyValue('--bg-surface0').trim() || '#0d1117'
  const borderColor = cs.getPropertyValue('--border').trim() || '#283044'
  const textPrimary = cs.getPropertyValue('--text-primary').trim() || '#e2e8f0'
  const fontMono = cs.getPropertyValue('--font-family-mono').trim() || 'monospace'

  const reportedColor = 'var(--green)'
  const estimatedColor = 'var(--runtime)'

  return (
    <ResponsiveContainer width="100%" height={180}>
      <BarChart data={data} margin={{ left: 0, right: 16, top: 4, bottom: 0 }}>
        <XAxis
          dataKey="date"
          tickFormatter={formatDate}
          tick={{ fontSize: 10, fill: textMuted, fontFamily: fontMono }}
          tickLine={false}
          axisLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          tickFormatter={formatDollar}
          tick={{ fontSize: 10, fill: textMuted, fontFamily: fontMono }}
          tickLine={false}
          axisLine={false}
          width={72}
        />
        <Tooltip
          formatter={(value, name) => [
            formatDollar(Number(value ?? 0)),
            name === 'costReported' ? 'Reported' : 'Estimated',
          ]}
          labelFormatter={(label) => formatDate(String(label ?? ''))}
          contentStyle={{
            background: bgSurface0,
            border: `1px solid ${borderColor}`,
            color: textPrimary,
            fontSize: 12,
          }}
        />
        <Legend
          verticalAlign="top"
          height={28}
          formatter={(value: string) => value === 'costReported' ? 'Reported' : 'Estimated'}
        />
        <Bar dataKey="costReported" stackId="cost" fill={reportedColor} barSize={10} name="costReported" />
        <Bar dataKey="costEstimated" stackId="cost" fill={estimatedColor} opacity={0.5} barSize={10} name="costEstimated" />
      </BarChart>
    </ResponsiveContainer>
  )
}
