import React, { useState, useEffect } from 'react'
import { GitBranch, Folder, Globe, Plus, Columns2, List, LayoutGrid, ChevronDown, Check, X } from 'lucide-react'
import type { BoardScope, Direction, Preset } from './types'
import { SCOPES } from './constants'
import s from './CommandCenterHeader.module.css'

export interface CommandCenterHeaderProps {
  sections: BoardScope[]
  preset: Preset
  direction: Direction
  featurePending: number
  onToggleSection: (scope: BoardScope) => void
  onAddSection: () => void
  onToggleDirection: () => void
  onApplyPreset: (preset: 'board' | 'pipeline' | 'focus') => void
}

const SCOPE_ICONS: Record<BoardScope, React.ReactNode> = {
  feature: <GitBranch size={13} />,
  project: <Folder size={13} />,
  global:  <Globe size={13} />,
}

const PRESET_ITEMS: Array<{ id: 'board' | 'pipeline' | 'focus'; name: string; desc: string }> = [
  { id: 'board',    name: 'Board view',    desc: 'Global · Project · Feature' },
  { id: 'pipeline', name: 'Pipeline view', desc: 'Feature + features rail' },
  { id: 'focus',    name: 'Focus',         desc: 'Feature board, full width' },
]

// Workspace header: section tabs (multi-select), layout direction toggle,
// presets menu, exit.
export function CommandCenterHeader(p: CommandCenterHeaderProps) {
  const [menu, setMenu] = useState(false)

  useEffect(() => {
    if (!menu) return
    const close = () => setMenu(false)
    document.addEventListener('click', close)
    return () => document.removeEventListener('click', close)
  }, [menu])

  return (
    <div className={s.head}>
      <div className={s.brand}><span className={s.dot}>◈</span>Command Center</div>

      <div className={s.tabs}>
        {(['feature', 'project', 'global'] as BoardScope[]).map((sc) => {
          const on = p.sections.indexOf(sc) > -1
          const pend = sc === 'feature' ? p.featurePending : 0
          return (
            <button
              key={sc}
              type="button"
              className={s.tab}
              {...(on ? { 'data-on': '' } : {})}
              aria-pressed={on}
              onClick={() => p.onToggleSection(sc)}
            >
              {SCOPE_ICONS[sc]}
              <span>{SCOPES[sc].label}</span>
              <span className={s.st}>{on ? '●' : '○'}</span>
              {pend > 0 && <span className={`${s.badge} ${s.msg}`}>{pend}</span>}
            </button>
          )
        })}
        <button
          type="button"
          className={`${s.tab} ${s.add}`}
          title="Toggle a board section"
          onClick={p.onAddSection}
        >
          <Plus size={13} />Add
        </button>
      </div>

      <div className={s.headRight}>
        {p.sections.length >= 2 && (
          <button type="button" className={s.ctl} onClick={p.onToggleDirection}>
            {p.direction === 'row' ? <Columns2 size={13} /> : <List size={13} />}
            {p.direction === 'row' ? 'side by side' : 'stacked'}
          </button>
        )}
        <div className={s.menuWrap}>
          <button
            type="button"
            className={s.ctl}
            aria-haspopup="listbox"
            {...(menu ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
            onClick={(e) => { e.stopPropagation(); setMenu((m) => !m) }}
          >
            <LayoutGrid size={13} />Presets<ChevronDown size={12} />
          </button>
          <div className={s.menu} {...(menu ? { 'data-open': '' } : {})}>
            {PRESET_ITEMS.map((it) => (
              <button
                key={it.id}
                type="button"
                className={s.menuItem}
                {...(p.preset === it.id ? { 'data-active': '' } : {})}
                onClick={() => p.onApplyPreset(it.id)}
              >
                {p.preset === it.id ? <Check size={13} /> : <span className={s.iconSpacer} />}
                <span>{it.name}</span>
                <span className={s.desc}>{it.desc}</span>
              </button>
            ))}
          </div>
        </div>
        <button type="button" className={`${s.ctl} ${s.exit}`} title="Exit Command Center">
          <X size={15} />
        </button>
      </div>
    </div>
  )
}
