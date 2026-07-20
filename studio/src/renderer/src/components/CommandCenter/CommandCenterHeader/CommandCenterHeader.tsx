import React, { useState, useEffect, useRef, useCallback } from 'react'
import { GitBranch, Folder, Globe, Plus, LayoutGrid, ChevronDown, Check, X, FolderPlus } from 'lucide-react'
import type { BoardScope, Preset, SectionDef } from '../types'
import { SCOPES } from '../constants'
import { Tooltip, CreatePopover, slugify } from '../../ui'
import { RESERVED_TOPICS } from '../../../store/reservedTopics'
import { GlobalSearch } from '../GlobalSearch/GlobalSearch'
import type { GlobalSearchHit } from '../../../store/commsStore'
import s from './CommandCenterHeader.module.css'

export interface CommandCenterHeaderProps {
  sections: SectionDef[]
  featureTabs: string[]
  preset: Preset
  mainFeature: string
  featurePending: number
  atCap: boolean
  onToggleSection: (scope: 'project' | 'global') => void
  onToggleFeatureSection: (fid: string) => void
  onRemoveFeatureTab: (fid: string) => void
  onAddSection: () => void
  onApplyPreset: (preset: 'board' | 'pipeline' | 'focus') => void
  onCreateFeature: (topic: string, description: string) => void
  /** Navigate to a global-search hit's board and flash the matched message. */
  onOpenSearchResult: (hit: GlobalSearchHit) => void
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

export function CommandCenterHeader(p: CommandCenterHeaderProps): JSX.Element {
  const [menu, setMenu] = useState(false)
  const headRef = useRef<HTMLDivElement>(null)
  const [compact, setCompact] = useState(false)
  const newFeatureBtnRef = useRef<HTMLButtonElement>(null)
  const [showNewFeature, setShowNewFeature] = useState(false)

  const checkCompact = useCallback(() => {
    const el = headRef.current
    if (!el) return
    // Brand ~220px + headRight (search icon ~34 + New feature icon ~34 + Presets ~110) + gaps
    // ~30px + ~122px per tab. Presets collapses to an icon past this point (data-compact), so
    // this is the labels-shown width we size against.
    const headRightPx = 200
    const needed = 220 + headRightPx + (2 + p.featureTabs.length) * 122
    setCompact(el.offsetWidth < needed)
  }, [p.featureTabs.length])

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
        <Tooltip
          label={`${SCOPES['global'].label} board`}
          description={globalOn ? 'Showing · click to hide' : 'Hidden · click to show'}
          placement="bottom"
        >
          <button
            type="button"
            className={s.tab}
            {...(globalOn ? { 'data-on': '' } : {})}
            {...(globalOn ? { 'aria-pressed': 'true' } : { 'aria-pressed': 'false' })}
            onClick={() => p.onToggleSection('global')}
          >
            {SCOPE_ICONS['global']}
            <span className={s.tabLabel}>{SCOPES['global'].label}</span>
          </button>
        </Tooltip>

        {/* Project tab — second */}
        <Tooltip
          label={`${SCOPES['project'].label} board`}
          description={projectOn ? 'Showing · click to hide' : 'Hidden · click to show'}
          placement="bottom"
        >
          <button
            type="button"
            className={s.tab}
            {...(projectOn ? { 'data-on': '' } : {})}
            {...(projectOn ? { 'aria-pressed': 'true' } : { 'aria-pressed': 'false' })}
            onClick={() => p.onToggleSection('project')}
          >
            {SCOPE_ICONS['project']}
            <span className={s.tabLabel}>{SCOPES['project'].label}</span>
          </button>
        </Tooltip>

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
            >
              <Tooltip
                label={fid}
                description={isActive ? 'Showing · click to hide' : 'Hidden · click to show'}
                placement="bottom"
              >
                <button
                  type="button"
                  className={s.tabToggle}
                  {...(isActive ? { 'aria-pressed': 'true' } : { 'aria-pressed': 'false' })}
                  onClick={() => p.onToggleFeatureSection(fid)}
                >
                  <GitBranch size={13} />
                  <span className={s.tabLabel}>{fid}</span>
                  {pend > 0 && <span className={`${s.badge} ${s.msg}`}>{pend}</span>}
                </button>
              </Tooltip>
              {!isOnly && (
                <button
                  type="button"
                  className={s.tabClose}
                  aria-label={`Remove ${fid} tab`}
                  onClick={() => p.onRemoveFeatureTab(fid)}
                >
                  <X size={11} />
                </button>
              )}
            </div>
          )
        })}

        {/* + Add button — only for project/global panels */}
        {canAdd && (
          <Tooltip label="Add a board section" placement="bottom">
            <button
              type="button"
              className={`${s.tab} ${s.add}`}
              onClick={p.onAddSection}
            >
              <Plus size={13} /><span className={s.tabLabel}>Add</span>
            </button>
          </Tooltip>
        )}
      </div>

      <div className={s.headRight} {...(compact ? { 'data-compact': '' } : {})}>
        <GlobalSearch onOpenResult={p.onOpenSearchResult} />
        <Tooltip label="New feature" description="Create a feature folder and open its board" placement="bottom">
          <button
            ref={newFeatureBtnRef}
            type="button"
            className={`${s.ctl} ${s.newFeature}`}
            aria-label="New feature"
            {...(showNewFeature ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
            onClick={() => setShowNewFeature(true)}
          >
            <FolderPlus size={13} />
          </button>
        </Tooltip>
        {showNewFeature && (
          <CreatePopover
            anchorEl={newFeatureBtnRef.current}
            heading="New feature"
            titleLabel="Title"
            titlePlaceholder="e.g. RTK token killer"
            descLabel="Description"
            descPlaceholder="What is this feature about?"
            showSlug
            validate={(slug) => (RESERVED_TOPICS.has(slug) ? `"${slug}" is a reserved name — choose another` : null)}
            onSubmit={(title, desc) => { p.onCreateFeature(slugify(title), desc); setShowNewFeature(false) }}
            onClose={() => setShowNewFeature(false)}
          />
        )}

        <div className={s.menuWrap}>
          <button
            type="button"
            className={s.ctl}
            title="Presets"
            aria-haspopup="listbox"
            {...(menu ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
            onClick={(e) => { e.stopPropagation(); setMenu((m) => !m) }}
          >
            <LayoutGrid size={13} /><span className={s.presetLabel}>Presets</span><ChevronDown size={12} className={s.presetChevron} />
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
