import type { PricingTable } from '../costUtils'
import { useTrends } from './useTrends'
import type { CsvRow } from './useTrends'
import { DailyCostChart } from './DailyCostChart'
import { ActivityHeatmap } from './ActivityHeatmap'
import { CacheEfficiencyChart } from './CacheEfficiencyChart'
import styles from './TrendsTab.module.css'

interface TrendsTabProps {
  featureName: string
  events: DbEvent[]
  pricingTable: PricingTable | null
}

const CSV_HEADERS: (keyof CsvRow)[] = [
  'ts', 'agent', 'model', 'provider',
  'input_tokens', 'output_tokens', 'total_tokens',
  'cache_read_tokens', 'cache_write_tokens',
  'cost_usd', 'cost_source', 'wall_seconds', 'feature',
]

function escapeCsv(val: string | number | null | undefined): string {
  const s = String(val ?? '')
  if (s.includes(',') || s.includes('"') || s.includes('\n')) {
    return `"${s.replace(/"/g, '""')}"`
  }
  return s
}

function buildCsvString(rows: CsvRow[]): string {
  const header = CSV_HEADERS.join(',')
  const lines = rows.map((row) =>
    CSV_HEADERS.map((k) => escapeCsv(row[k])).join(',')
  )
  return [header, ...lines].join('\n')
}

function sanitizeFilename(name: string): string {
  return name.replace(/[/\\]/g, '').replace(/ /g, '-')
}

export function TrendsTab({ featureName, events, pricingTable }: TrendsTabProps): JSX.Element {
  const { dailyCost, heatmapCells, csvRows, loading, error } = useTrends(featureName, events, pricingTable)

  function handleCsvExport(): void {
    const csv = buildCsvString(csvRows)
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${sanitizeFilename(featureName)}-agent-runs.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (loading) {
    return <p className={styles.empty}>Loading…</p>
  }

  if (error) {
    return <p className={styles.empty}>{error}</p>
  }

  return (
    <div className={styles.container}>
      <section className={styles.section}>
        <h4 className={styles.sectionHeading}>Daily Cost</h4>
        <DailyCostChart data={dailyCost} />
      </section>

      <section className={styles.section}>
        <h4 className={styles.sectionHeading}>Activity (18 weeks)</h4>
        <ActivityHeatmap cells={heatmapCells} />
      </section>

      <section className={styles.section}>
        <h4 className={styles.sectionHeading}>Cache Efficiency</h4>
        <CacheEfficiencyChart events={events} />
      </section>

      <section className={styles.section}>
        <button type="button" className={styles.csvBtn} onClick={handleCsvExport}>
          Export CSV
        </button>
      </section>
    </div>
  )
}
