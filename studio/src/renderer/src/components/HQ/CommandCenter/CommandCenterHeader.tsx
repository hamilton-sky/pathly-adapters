import React, { useState, useEffect, useRef, useCallback } from 'react'
import { GitBranch, Folder, Globe, Plus, Columns2, List, LayoutGrid, ChevronDown, Check, X } from 'lucide-react'
import type { BoardScope, Direction, Preset, SectionDef } from './types'
import { SCOPES } from './constants'
import s from './CommandCenterHeader.module.css'

export interface CommandCenterHeaderProps {
  sections: SectionDef[]
  featureTabs: string[]
  preset: Preset
  direction: Direction
  mainFeature: string
  featurePending: number
  atCap: boolean
  onToggleSection: (scope: 'project' | 'global') => void
  onToggleFeatureSection: (fid: string) => void
  onRemoveFeatureTab: (fid: string) => void
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

export function CommandCenterHeader(p: CommandCenterHeaderProps) {
  const [menu, setMenu] = useState(false)
  const headRef = useRef<HTMLDivElement>(null)
  const [compact, setCompact] = useState(false)

  const checkCompact = useCallback(() => {
    const el = headRef.current
    if (!el) return
    // Brand ~190px + headRight ~280px (with dirPill) or ~100px + gaps 30px + ~122px per tab
    const headRightPx = p.sections.length >= 2 ? 280 : 100
    const needed = 220 + headRightPx + (2 + p.featureTabs.length) * 122
    setCompact(el.offsetWidth < needed)
  }, [p.featureTabs.length, p.sections.length])

  useEffect(() => {
    const obs = new ResizeObserver(checkCompact)
    if (headRef.current) obs.observe(headRef.current)
    checkCompact()
    return () => obs.disconnect()
  }, [checkCompact])

  useEffect(() => {
    if (!menu) return
    const close = () => setMenu(false)
    document.addEventListener('click', close)
    return () => document.removeEventListener('click', close)
  }, [menu])

  const projectOn = p.sections.some((sec) => sec.scope === 'project')
  const globalOn  = p.sections.some((sec) => sec.scope === 'global')
  const isOnly = p.featureTabs.length <= 1
  const canAdd = !p.atCap && (!projectOn || !globalOn)

  return (
    <div ref={headRef} className={s.head}>
      <div className={s.brand}><span className={s.dot}>◈</span>Command Center</div>

      <div
        className={s.tabs}
        {...(compact ? { 'data-compact': '' } : {})}
      >
        {/* Global tab — first */}
        <button
          key="global"
          type="button"
          className={s.tab}
          title={`Toggle the ${SCOPES['global'].label} board`}
          {...(globalOn ? { 'data-on': '' } : {})}
          aria-pressed={globalOn}
          onClick={() => p.onToggleSection('global')}
        >
          {SCOPE_ICONS['global']}
          <span className={s.tabLabel}>{SCOPES['global'].label}</span>
          <span className={s.st}>{globalOn ? '●' : '○'}</span>
        </button>

        {/* Project tab — second */}
        <button
          key="project"
          type="button"
          className={s.tab}
          title={`Toggle the ${SCOPES['project'].label} board`}
          {...(projectOn ? { 'data-on': '' } : {})}
          aria-pressed={projectOn}
          onClick={() => p.onToggleSection('project')}
        >
          {SCOPE_ICONS['project']}
          <span className={s.tabLabel}>{SCOPES['project'].label}</span>
          <span className={s.st}>{projectOn ? '●' : '○'}</span>
        </button>

        {/* Feature tabs — one per featureTabs entry */}
        {p.featureTabs.map((fid) => {
          const isActive = p.sections.some(
            (sec): sec is Extract<SectionDef, { scope: 'feature' }> => sec.scope === 'feature' && sec.featureId === fid
          )
          const pend = fid === p.mainFeature ? p.featurePending : 0
          return (
            <div
              key={fid}
              className={`${s.tab} ${s.featureTab}`}
              {...(isActive ? { 'data-on': '' } : {})}
              role="button"
              tabIndex={0}
              title={isActive ? `Hide ${fid} panel` : `Show ${fid} panel`}
              onClick={() => p.onToggleFeatureSection(fid)}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') p.onToggleFeatureSection(fid) }}
            >
              <GitBranch size={13} />
              <span className={s.tabLabel}>{fid}</span>
              <span className={s.st}>{isActive ? '●' : '○'}</span>
              {pend > 0 && <span className={`${s.badge} ${s.msg}`}>{pend}</span>}
              {!isOnly && (
                <button
                  type="button"
                  className={s.tabClose}
                  title={`Remove ${fid} tab`}
                  aria-label={`Remove ${fid} tab`}
                  onClick={(e) => { e.stopPropagation(); p.onRemoveFeatureTab(fid) }}
                >
                  <X size={11} />
                </button>
              )}
            </div>
          )
        })}

        {/* + Add button — only for project/global panels */}
        {canAdd && (
          <button
            type="button"
            className={`${s.tab} ${s.add}`}
            title="Add a board section"
            onClick={p.onAddSection}
          >
            <Plus size={13} /><span className={s.tabLabel}>Add</span>
          </button>
        )}
      </div>

      <div className={s.headRight}>
        {p.sections.length >= 2 && (
          <div className={s.dirPill}>
            <button
              type="button"
              className={s.dirOpt}
              {...(p.direction === 'column' ? { 'data-active': '' } : {})}
              aria-pressed={p.direction === 'column'}
              title="Stacked layout"
              onClick={() => p.direction !== 'column' && p.onToggleDirection()}
            >
              <List size={13} />Stacked
            </button>
            <button
              type="button"
              className={s.dirOpt}
              {...(p.direction === 'row' ? { 'data-active': '' } : {})}
              aria-pressed={p.direction === 'row'}
              title="Side by side layout"
              onClick={() => p.direction !== 'row' && p.onToggleDirection()}
            >
              <Columns2 size={13} />Side by side
            </button>
          </div>
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
      </div>
    </div>
  )
}
