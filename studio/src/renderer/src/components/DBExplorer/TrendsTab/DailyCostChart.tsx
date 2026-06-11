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

  const reportedColor = 'var(--green)'
  const estimatedColor = 'var(--runtime)'

  return (
    <ResponsiveContainer width="100%" height={180}>
      <BarChart data={data} margin={{ left: 0, right: 16, top: 4, bottom: 0 }}>
        <XAxis
          dataKey="date"
          tickFormatter={formatDate}
          tick={{ fontSize: 'var(--font-size-xs)', fill: 'var(--text-muted)', fontFamily: 'var(--font-family-mono)' }}
          tickLine={false}
          axisLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          tickFormatter={formatDollar}
          tick={{ fontSize: 'var(--font-size-xs)', fill: 'var(--text-muted)', fontFamily: 'var(--font-family-mono)' }}
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
            background: 'var(--bg-mantle)',
            border: '1px solid var(--border-color)',
            color: 'var(--text-primary)',
            fontSize: 'var(--font-size-sm)',
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
