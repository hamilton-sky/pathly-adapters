import { useState } from 'react'
import type { FeatureData, LayoutMode, MetricKey, ViewMode } from './types'
import { StatsStrip } from './StatsStrip'
import { CollapsibleCostChart } from './CollapsibleCostChart'
import { CircularMetric } from './CircularMetric'
import { SegmentedToggle } from './SegmentedToggle'
import { FeatureCard } from './FeatureCard'
import { FeatureStack } from './FeatureStack'
import { RollupView } from './RollupView'
import { FeaturePreview } from './FeaturePreview'
import { FeatureDetailPage } from './FeatureDetailPage'
import { useDbExplorerData } from './hooks/useDbExplorerData'
import styles from './DBExplorerRedesign.module.css'

// Only B (equal split) and C (stacked) are offered — A was dropped.
const LAYOUT_OPTIONS: { label: string; value: LayoutMode; title: string }[] = [
  { label: 'B', value: 'B', title: 'Equal split — chart + metric side by side' },
  { label: 'C', value: 'C', title: 'Stacked — chart then metric, full width' },
]

const VIEW_OPTIONS: { icon: string; value: ViewMode; title: string }[] = [
  { icon: '⊞', value: 'grid', title: 'Grid view' },
  { icon: '☰', value: 'stack', title: 'Stack view' },
  { icon: 'Σ', value: 'rollup', title: 'Roll-up view (feature → project → global)' },
]

function exportJson(topStats: unknown, features: unknown): void {
  const blob = new Blob([JSON.stringify({ topStats, features }, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'db-explorer.json'
  a.click()
  URL.revokeObjectURL(url)
}

/**
 * Redesigned DB Explorer panel, wired to live window.pathly.db.* data.
 *
 *  - Cost chart collapses to its summary numbers (collapsed by default).
 *  - Half-width circular metric (donut) beside the chart, switchable across
 *    four live aggregations; a B/C layout switch rearranges the row.
 *  - ⊞ / ☰ / Σ view toggle → card grid / list stack / roll-up.
 *  - Cards open a preview popover; preview (or card ↗) routes to a full
 *    detail PAGE with the shipped live Timeline / Events / Agents / Traces /
 *    Inspect / Trends tabs.
 */
export function DBExplorerRedesign(): JSX.Element {
  const {
    features, topStats, chart, tokenSplit, agentRoles,
    loading, costLoading, scope, setScope, range, setRange, refresh,
  } = useDbExplorerData()

  const [metric, setMetric] = useState<MetricKey>('state')
  const [layout, setLayout] = useState<LayoutMode>('B')
  const [view, setView] = useState<ViewMode>('grid')
  const [preview, setPreview] = useState<FeatureData | null>(null)
  const [detail, setDetail] = useState<FeatureData | null>(null)

  const openDetail = (f: FeatureData): void => { setDetail(f); setPreview(null) }

  if (detail) {
    return <FeatureDetailPage feature={detail} onBack={() => setDetail(null)} />
  }

  return (
    <div className={styles.panel}>
      <header className={styles.header}>
        <div className={styles.titleGroup}>
          <h2 className={styles.title}>DB Explorer</h2>
          <span className={styles.subtitle}>Pipeline database — features, events, agent invocations</span>
        </div>
        <div className={styles.actions}>
          <span className={styles.layoutLabel}>Layout</span>
          <SegmentedToggle options={LAYOUT_OPTIONS} value={layout} onChange={setLayout} ariaLabel="Chart layout" />
          <span className={styles.divider} />
          <div className={styles.viewToggle}>
            {VIEW_OPTIONS.map((v) => (
              <button
                key={v.value}
                type="button"
                title={v.title}
                aria-label={v.title}
                className={`${styles.toggleBtn} ${view === v.value ? styles.toggleBtnActive : ''}`}
                onClick={() => setView(v.value)}
              >
                {v.icon}
              </button>
            ))}
          </div>
          <button type="button" className={styles.btnB} onClick={refresh}>↻ Refresh</button>
          <button type="button" className={styles.btnB} onClick={() => exportJson(topStats, features)}>↓ Export JSON</button>
        </div>
      </header>

      <StatsStrip stats={topStats} />

      <section className={styles.chartSection}>
        <div className={styles.chartRow} data-layout={layout}>
          <CollapsibleCostChart
            series={chart.series}
            startDate={chart.startDate}
            peakIndex={chart.peakIndex}
            total={chart.total}
            avgPerActiveDay={chart.avgPerActiveDay}
            peak={chart.peak}
            peakDay={chart.peakDay}
            spanCount={chart.spanCount}
            scope={scope}
            onScope={setScope}
            range={range}
            onRange={setRange}
            loading={costLoading}
          />
          <CircularMetric inputs={{ features, tokenSplit, agentRoles }} metric={metric} onMetric={setMetric} />
        </div>
      </section>

      {loading && features.length === 0 ? (
        <div className={styles.loading}>Loading…</div>
      ) : (
        <>
          {view === 'grid' && (
            features.length === 0
              ? <div className={styles.loading}>No features yet.</div>
              : (
                <section className={styles.grid}>
                  {features.map((f) => (
                    <FeatureCard key={f.name} feature={f} onPreview={setPreview} onOpenDetail={openDetail} />
                  ))}
                </section>
              )
          )}
          {view === 'stack' && <FeatureStack features={features} onRowClick={setPreview} />}
          {view === 'rollup' && <RollupView />}
        </>
      )}

      <FeaturePreview feature={preview} onClose={() => setPreview(null)} onOpenDetail={openDetail} />
    </div>
  )
}
