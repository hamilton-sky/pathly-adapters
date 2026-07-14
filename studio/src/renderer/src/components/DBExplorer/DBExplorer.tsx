import { useState, useEffect, useCallback } from 'react'
import { useProjectStore } from '../../store/projectStore'
import type { FeatureData } from './dbExplorerData'
import { StatsStrip } from './StatsStrip'
import { FeatureGrid } from './FeatureGrid'
import FeatureStack from './FeatureStack'
import { FeatureModal } from './FeatureModal'
import { CostOverTimeChart, type CostPoint, type ScopeMode, type RangeDays } from './CostOverTimeChart'
import { RollupView } from './RollupView/RollupView'
import styles from './DBExplorer.module.css'

type ViewMode = 'grid' | 'stack' | 'rollup'

function bucketToCostPoint(b: DailyTrendBucket): CostPoint {
  return {
    day: b.bucket,
    cost_usd: b.cost_usd_reported,
    tokens: b.input_tokens,
    span_count: b.count,
  }
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
    ts: f.updated_at ? f.updated_at.slice(11, 19) : '',
    pcol: `var(--state-${state.toLowerCase()})`,
    dots: [{ state }],
  }
}

function mapState(s: string): FeatureData['state'] {
  const upper = s.toUpperCase()
  if (upper === 'DONE') return 'DONE'
  if (upper === 'RETRO') return 'RETRO'
  if (['TESTING', 'TEST'].includes(upper)) return 'TESTING'
  if (['REVIEWING', 'REVIEW'].includes(upper)) return 'REVIEWING'
  if (['BUILDING', 'BUILD', 'DESIGN', 'DESIGNING'].includes(upper)) return 'BUILDING'
  // STORM, PLAN, PLANNING, UNKNOWN and anything else → PLANNING
  return 'PLANNING'
}

export function DBExplorer(): JSX.Element {
  const projectPath = useProjectStore((s) => s.projectPath)
  const [features, setFeatures] = useState<FeatureData[]>([])
  const [stats, setStats] = useState<DbStats | null>(null)
  const [modalFeature, setModalFeature] = useState<FeatureData | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const [loading, setLoading] = useState(true)
  const [costPoints, setCostPoints] = useState<CostPoint[]>([])
  const [costScope, setCostScope] = useState<ScopeMode>('project')
  const [costRange, setCostRange] = useState<RangeDays>(30)
  const [costLoading, setCostLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [rawFeatures, rawStats] = await Promise.all([
        window.pathly.db.features(projectPath || undefined),
        window.pathly.db.stats(projectPath || undefined),
      ])
      setFeatures(rawFeatures.map(dbFeatureToFeatureData))
      setStats(rawStats)
    } catch {
      // FSM may not be running yet — stay with empty list
    } finally {
      setLoading(false)
    }
  }, [projectPath])

  // Cost-over-time trends load on their own axis: the Project/Global scope switch
  // (and a re-scope) must refetch the chart without reloading the whole panel.
  const loadTrends = useCallback(async () => {
    setCostLoading(true)
    try {
      const root = costScope === 'global' ? undefined : projectPath || undefined
      const rawTrends = await window.pathly.db.trends('', costRange, root)
      setCostPoints((rawTrends?.trends ?? []).map(bucketToCostPoint))
    } catch {
      setCostPoints([])
    } finally {
      setCostLoading(false)
    }
  }, [projectPath, costScope, costRange])

  useEffect(() => { load() }, [load])
  useEffect(() => { loadTrends() }, [loadTrends])

  const refresh = useCallback(() => {
    load()
    loadTrends()
  }, [load, loadTrends])

  return (
    <div className={styles.panel}>
      <DBExplorerHeader viewMode={viewMode} onViewMode={setViewMode} onRefresh={refresh} />
      <StatsStrip stats={stats} features={features} />
      <div className={styles.chartSection}>
        <CostOverTimeChart
          points={costPoints}
          loading={costLoading}
          range={costRange}
          onRange={setCostRange}
          scope={costScope}
          onScope={setCostScope}
        />
      </div>
      {loading
        ? <div className={styles.loading}>Loading…</div>
        : viewMode === 'rollup'
          ? <RollupView />
          : viewMode === 'grid'
            ? <FeatureGrid features={features} onCardClick={setModalFeature} />
            : <FeatureStack features={features} onRowClick={setModalFeature} />
      }
      <FeatureModal feature={modalFeature} onClose={() => setModalFeature(null)} />
    </div>
  )
}

interface HeaderProps {
  viewMode: ViewMode
  onViewMode: (m: ViewMode) => void
  onRefresh: () => void
}

function DBExplorerHeader({ viewMode, onViewMode, onRefresh }: HeaderProps): JSX.Element {
  return (
    <div className={styles.header}>
      <div className={styles.titleGroup}>
        <h2 className={styles.title}>DB Explorer</h2>
        <span className={styles.subtitle}>Pipeline database — features, events, agent invocations</span>
      </div>
      <div className={styles.actions}>
        <div className={styles.viewToggle}>
          <button
            type="button"
            className={`${styles.toggleBtn} ${viewMode === 'grid' ? styles.toggleBtnActive : ''}`}
            onClick={() => onViewMode('grid')}
            aria-label="Grid view"
            {...(viewMode === 'grid' ? { 'aria-pressed': 'true' } : { 'aria-pressed': 'false' })}
          >
            ⊞
          </button>
          <button
            type="button"
            className={`${styles.toggleBtn} ${viewMode === 'stack' ? styles.toggleBtnActive : ''}`}
            onClick={() => onViewMode('stack')}
            aria-label="Stack view"
            {...(viewMode === 'stack' ? { 'aria-pressed': 'true' } : { 'aria-pressed': 'false' })}
          >
            ☰
          </button>
          <button
            type="button"
            className={`${styles.toggleBtn} ${viewMode === 'rollup' ? styles.toggleBtnActive : ''}`}
            onClick={() => onViewMode('rollup')}
            aria-label="Roll-up view (feature → project → global)"
            {...(viewMode === 'rollup' ? { 'aria-pressed': 'true' } : { 'aria-pressed': 'false' })}
          >
            Σ
          </button>
        </div>
        <button type="button" className={styles.btnB} onClick={onRefresh}>↻ Refresh</button>
        <button type="button" className={styles.btnB}>↓ Export JSON</button>
      </div>
    </div>
  )
}
