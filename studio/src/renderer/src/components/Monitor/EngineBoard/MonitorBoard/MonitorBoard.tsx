import { useMemo, useState } from 'react'
import type { EngineAdapter, MonitorEngine } from '../types'
import { CATEGORY_META } from '../constants'
import { CategoryFilterBar, type CategoryFilter } from '../CategoryFilterBar/CategoryFilterBar'
import { ScopeFilter } from '../ScopeFilter/ScopeFilter'
import { EngineSection } from '../EngineSection/EngineSection'
import { EngineDetailModal } from '../EngineDetailModal/EngineDetailModal'
import { MonitorBoardHeader, type BoardMode } from './MonitorBoardHeader/MonitorBoardHeader'
import { RunList } from '../../RunList/RunList'
import { useRuns } from '../../RunList/hooks/useRuns'
import { NewRunButton } from '../../RunList/NewRunButton/NewRunButton'
import { adapterFromProvider } from '../../../RunDetailPage/runAdapter'
import s from './MonitorBoard.module.css'

interface Props {
  /** Live engines — map from your runner/terminal store. */
  engines: MonitorEngine[]
  /** Recently-finished spawns (DB-backed history) — rendered as a 'Recent' section. */
  recent?: MonitorEngine[]
  /** Fired when a control button in the detail modal is pressed. */
  onAction?: (engineId: string, actionId: string) => void
  /** Open the full RunDetailPage for a run (detail modal's "Open run →" + a Runs-mode row). */
  onOpenRun?: (runId: string) => void
}

// The Monitor board has two modes (MonitorBoardHeader toggle): LIVE — the per-spawn engine board
// grouped by category (Flow/Loop/Single) + a Recent history section; and RUNS — the folded
// one-row-per-top-level-run list from GET /runs (a flow's stage spawns collapse to one row).
// Category / adapter / scope filters and their counts apply to whichever mode is active.
export function MonitorBoard({ engines, recent, onAction, onOpenRun }: Props): JSX.Element {
  const [mode, setMode] = useState<BoardMode>('live')
  const [category, setCategory] = useState<CategoryFilter>('all')
  const [adapter, setAdapter] = useState<EngineAdapter | null>(null)
  const [scope, setScope] = useState<string | null>(null)
  const [openId, setOpenId] = useState<string | null>(null)
  const [view, setView] = useState<'grid' | 'banner'>('grid')

  // Lazy: the /runs poll only runs while Runs mode is open (the Live board is the default).
  const { runs, loading: runsLoading, refetch: refetchRuns } = useRuns(mode === 'runs')

  const running = useMemo(() => engines.filter((e) => e.status === 'running').length, [engines])
  const queued = useMemo(() => engines.filter((e) => e.status === 'queued').length, [engines])

  // Counts + scopes derive from the ACTIVE mode's source array, so the filter tabs never mismatch
  // the rows shown (a "Flow (4)" chip over 2 visible rows reads as a bug).
  const counts = useMemo(() => {
    const c: Record<string, number> = {}
    if (mode === 'runs') {
      c.all = runs.length
      for (const r of runs) c[r.kind] = (c[r.kind] ?? 0) + 1
    } else {
      const all = [...engines, ...(recent ?? [])]
      c.all = all.length
      for (const e of all) c[e.category] = (c[e.category] ?? 0) + 1
    }
    return c
  }, [mode, runs, engines, recent])

  const scopes = useMemo(() => {
    const src = mode === 'runs' ? runs.map((r) => r.feature) : engines.map((e) => e.feature)
    return Array.from(new Set(src)).sort()
  }, [mode, runs, engines])

  // Live-mode derivations
  const filtered = engines.filter(
    (e) => (adapter === null || e.adapter === adapter) && (scope === null || e.feature === scope),
  )
  const sections = CATEGORY_META
    .filter((m) => category === 'all' || category === m.key)
    .map((m) => ({ meta: m, engines: filtered.filter((e) => e.category === m.key) }))
    .filter((sec) => sec.engines.length > 0)
  const recentFiltered = (recent ?? []).filter(
    (e) =>
      (category === 'all' || category === e.category) &&
      (adapter === null || e.adapter === adapter) &&
      (scope === null || e.feature === scope),
  )

  // Runs-mode derivation (kind==='decompose' has no chip → only visible under "All", accepted gap)
  const filteredRuns = runs.filter(
    (r) =>
      (category === 'all' || r.kind === category) &&
      (adapter === null || adapterFromProvider(r.adapter) === adapter) &&
      (scope === null || r.feature === scope),
  )

  const open = openId
    ? engines.find((e) => e.id === openId) ?? (recent ?? []).find((e) => e.id === openId) ?? null
    : null

  return (
    <div className={s.root}>
      <div className={s.inner}>
        <MonitorBoardHeader
          running={running}
          queued={queued}
          mode={mode}
          onMode={setMode}
          view={view}
          onView={setView}
        />

        <CategoryFilterBar
          category={category}
          onCategory={setCategory}
          adapter={adapter}
          onAdapter={setAdapter}
          counts={counts}
        />
        <ScopeFilter scopes={scopes} value={scope} onChange={setScope} />

        {mode === 'runs' ? (
          <>
            <div className={s.runsToolbar}>
              <NewRunButton onCreated={refetchRuns} />
            </div>
            {queued > 0 && (
              <p className={s.note}>{queued} queued — view on the Live board (the run list can’t show the gate queue).</p>
            )}
            <RunList runs={filteredRuns} loading={runsLoading} hasAny={runs.length > 0} view={view} onOpenRun={onOpenRun} />
          </>
        ) : (
          <>
            {sections.map((sec) => (
              <EngineSection
                key={sec.meta.key}
                meta={sec.meta}
                engines={sec.engines}
                view={view}
                onOpen={setOpenId}
                onAction={onAction}
              />
            ))}
            {recentFiltered.length > 0 && (
              <EngineSection
                key="recent"
                meta={{ key: 'single', label: 'Recent', blurb: 'finished · from history', color: 'var(--text-muted)' }}
                engines={recentFiltered}
                view={view}
                onOpen={setOpenId}
                onAction={onAction}
              />
            )}
            {sections.length === 0 && recentFiltered.length === 0 && (
              <p className={s.empty}>No engines in this view</p>
            )}
          </>
        )}
      </div>

      {open && (
        <EngineDetailModal
          engine={open}
          onClose={() => setOpenId(null)}
          onAction={onAction}
          onOpenRun={onOpenRun ? (id) => { setOpenId(null); onOpenRun(id) } : undefined}
        />
      )}
    </div>
  )
}
