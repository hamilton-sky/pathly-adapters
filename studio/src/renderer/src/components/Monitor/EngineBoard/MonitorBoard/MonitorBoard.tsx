import React, { useMemo, useState } from 'react'
import { LayoutGrid, Rows3 } from 'lucide-react'
import type { EngineAdapter, MonitorEngine } from '../types'
import { CATEGORY_META } from '../constants'
import { CategoryFilterBar, type CategoryFilter } from '../CategoryFilterBar/CategoryFilterBar'
import { ScopeFilter } from '../ScopeFilter/ScopeFilter'
import { EngineSection } from '../EngineSection/EngineSection'
import { EngineDetailModal } from '../EngineDetailModal/EngineDetailModal'
import s from './MonitorBoard.module.css'

interface Props {
  /** Live engines — map from your runner/terminal store. */
  engines: MonitorEngine[]
  /** Recently-finished spawns (DB-backed history) — rendered as a 'Recent' section. */
  recent?: MonitorEngine[]
  /** Fired when a control button in the detail modal is pressed. */
  onAction?: (engineId: string, actionId: string) => void
  /** Open the full RunDetailPage for a run (threaded to the detail modal's "Open run →"). */
  onOpenRun?: (runId: string) => void
}

// The Monitor board: a CLI-engine board that groups engines by how they run
// (Flow / Loop / Single), the same mechanism the Command Center uses to group
// messages by scope. Clicking a card opens its detail modal.
export function MonitorBoard({ engines, recent, onAction, onOpenRun }: Props): JSX.Element {
  const [category, setCategory] = useState<CategoryFilter>('all')
  const [adapter, setAdapter] = useState<EngineAdapter | null>(null)
  const [scope, setScope] = useState<string | null>(null)
  const [openId, setOpenId] = useState<string | null>(null)
  const [view, setView] = useState<'grid' | 'banner'>('grid')

  const counts = useMemo(() => {
    // Count live engines AND the recent-history cards, so the tabs reflect what is
    // actually on screen. Counting only `engines` showed Flow/Loop/Single = 0 whenever
    // nothing was live even though the Recent list was full of finished flow cards.
    const all = [...engines, ...(recent ?? [])]
    const c: Record<string, number> = { all: all.length }
    for (const e of all) c[e.category] = (c[e.category] ?? 0) + 1
    return c
  }, [engines, recent])

  const scopes = useMemo(
    () => Array.from(new Set(engines.map((e) => e.feature))).sort(),
    [engines],
  )

  const filtered = useMemo(
    () =>
      engines.filter(
        (e) =>
          (adapter === null || e.adapter === adapter) &&
          (scope === null || e.feature === scope),
      ),
    [engines, adapter, scope],
  )

  const running = useMemo(() => engines.filter((e) => e.status === 'running').length, [engines])
  const queued = useMemo(() => engines.filter((e) => e.status === 'queued').length, [engines])

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

  const open = openId
    ? engines.find((e) => e.id === openId) ?? (recent ?? []).find((e) => e.id === openId) ?? null
    : null

  return (
    <div className={s.root}>
      <div className={s.inner}>
        <header className={s.head}>
          <span className={s.title}>Monitor</span>
          <span className={s.summary}>{running} live · {queued} queued</span>
          <div className={s.viewToggle} role="group" aria-label="Card layout">
            <button
              type="button"
              className={s.viewBtn}
              data-active={view === 'grid'}
              onClick={() => setView('grid')}
              title="Grid of cards"
              aria-label="Grid view"
              {...(view === 'grid' ? { 'aria-pressed': 'true' } : { 'aria-pressed': 'false' })}
            >
              <LayoutGrid size={14} />
            </button>
            <button
              type="button"
              className={s.viewBtn}
              data-active={view === 'banner'}
              onClick={() => setView('banner')}
              title="Banner rows"
              aria-label="Banner view"
              {...(view === 'banner' ? { 'aria-pressed': 'true' } : { 'aria-pressed': 'false' })}
            >
              <Rows3 size={14} />
            </button>
          </div>
          <span className={s.live}>
            <span className={s.liveDot} />SSE live
          </span>
        </header>

        <CategoryFilterBar
          category={category}
          onCategory={setCategory}
          adapter={adapter}
          onAdapter={setAdapter}
          counts={counts}
        />

        <ScopeFilter scopes={scopes} value={scope} onChange={setScope} />

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
