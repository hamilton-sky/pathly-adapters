import React from 'react'
import { PanelLeft } from 'lucide-react'
import type { Feature } from './types'
import { FeatureCard } from './FeatureCard'
import s from './FeatureSidebar.module.css'

export interface FeatureSidebarProps {
  features: Feature[]
  openFeature: string | null
  mainFeature: string
  collapsed: boolean
  pendingCount: (id: string) => number
  openBoards: string[]
  atCap: boolean
  onToggleSidebar: () => void
  onToggleFeature: (id: string) => void
  onSetMain: (id: string) => void
  onRailOpen: (id: string) => void
  onOpenBoard: (id: string) => void
  onStatus: (id: string, status: 'running' | 'idle', stage?: 'BUILDING' | 'TESTING') => void
}

function CollapsedRail(p: FeatureSidebarProps) {
  return (
    <div className={`${s.sidebar} ${s.collapsed}`}>
      <div className={s.sbHead}>
        <button
          type="button"
          className={s.sbCollapse}
          title="Expand sidebar"
          aria-expanded={false}
          aria-label="Expand sidebar"
          onClick={p.onToggleSidebar}
        >
          <PanelLeft size={15} />
        </button>
        <span className={s.sbCountTiny}>{p.features.length}</span>
      </div>
      <div className={s.sbRail}>
        {p.features.map((f) => {
          const pend = p.pendingCount(f.id)
          const blocked = f.status === 'blocked'
          return (
            <button
              key={f.id}
              type="button"
              className={s.railbtn}
              title={f.id}
              aria-label={f.id}
              onClick={() => p.onRailOpen(f.id)}
            >
              <span className={`${s.featStdot} ${s[`st_${f.status}`]}`} />
              {(pend > 0 || blocked) && (
                <span className={`${s.railBadge}${blocked ? ` ${s.blk}` : ''}`}>
                  {blocked ? '!' : pend}
                </span>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}

export function FeatureSidebar(p: FeatureSidebarProps) {
  if (p.collapsed) return <CollapsedRail {...p} />

  return (
    <div className={s.sidebar}>
      <div className={s.sbHead}>
        <span className={s.sbTitle}>All Features</span>
        <span className={s.sbCount}>{p.features.length}</span>
        <button
          type="button"
          className={s.sbCollapse}
          title="Collapse sidebar"
          aria-expanded={true}
          aria-label="Collapse sidebar"
          onClick={p.onToggleSidebar}
        >
          <PanelLeft size={15} />
        </button>
      </div>
      <div className={s.sbList}>
        {p.features.map((f) => (
          <FeatureCard
            key={f.id}
            feature={f}
            open={p.openFeature === f.id}
            isMain={p.mainFeature === f.id}
            pending={p.pendingCount(f.id)}
            boardOpen={p.openBoards.includes(f.id)}
            atCap={p.atCap}
            onToggle={p.onToggleFeature}
            onSetMain={p.onSetMain}
            onOpenBoard={p.onOpenBoard}
            onStatus={p.onStatus}
          />
        ))}
      </div>
    </div>
  )
}
