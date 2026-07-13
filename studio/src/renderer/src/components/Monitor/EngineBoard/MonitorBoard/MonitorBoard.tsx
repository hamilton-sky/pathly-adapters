import React, { useMemo, useState } from 'react'
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
}

// The Monitor board: a CLI-engine board that groups engines by how they run
// (Flow / Loop / Single), the same mechanism the Command Center uses to group
// messages by scope. Clicking a card opens its detail modal.
export function MonitorBoard({ engines, recent, onAction }: Props): JSX.Element {
  const [category, setCategory] = useState<CategoryFilter>('all')
  const [adapter, setAdapter] = useState<EngineAdapter | null>(null)
  const [scope, setScope] = useState<string | null>(null)
  const [openId, setOpenId] = useState<string | null>(null)

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: engines.length }
    for (const e of engines) c[e.category] = (c[e.category] ?? 0) + 1
    return c
  }, [engines])

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
          <span className={s.live}>
            <span className={s.liveDot} />SSE live
          </span>
        </header>
        <p className={s.lede}>
          Every CLI engine is a card. Group by how it runs — single one-shot, loop cycle,
          or full flow — the way the board groups messages by scope.
        </p>

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
            onOpen={setOpenId}
            onAction={onAction}
          />
        ))}

        {recentFiltered.length > 0 && (
          <EngineSection
            key="recent"
            meta={{ key: 'single', label: 'Recent', blurb: 'finished · from history', color: 'var(--text-muted)' }}
            engines={recentFiltered}
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
        />
      )}
    </div>
  )
}
