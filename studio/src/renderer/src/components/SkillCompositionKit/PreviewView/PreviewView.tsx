import { useMemo } from 'react'
import type { PreviewRowVM, DrawerDetail } from '../types'
import { FRAGMENT_META, fragmentPurpose, fragmentTokens } from '../data/fragmentMeta'
import { ABILITIES } from '../data/abilities'
import { SYSTEM_BASE } from '../data/systemPrompt'
import { usePreviewInspector } from '../hooks/usePreviewInspector'
import { FragmentListPanel } from '../FragmentListPanel/FragmentListPanel'
import { ComposedPromptView } from '../ComposedPromptView/ComposedPromptView'
import { InspectDrawer } from '../InspectDrawer/InspectDrawer'
import styles from './PreviewView.module.css'

interface Props {
  skill: string
  fragments: string[]
  allFragments: string[]
  totalTokens: number
  onToggleFragment: (name: string) => void
}

/** Preview: tabbed fragment list (left) + live composed prompt (right, fixed top) with a
 *  slide-up inspect drawer. Row-name clicks never swap the composed view — only the eye does. */
export function PreviewView({ skill, fragments, allFragments, totalTokens, onToggleFragment }: Props): JSX.Element {
  const { tab, setTab, drawer, inspect, closeDrawer } = usePreviewInspector(skill)
  const on = (n: string): boolean => fragments.includes(n)

  const rows = useMemo<PreviewRowVM[]>(() => {
    if (tab === 'fragments') {
      return allFragments.map((n) => ({ id: n, kind: 'frag', label: n, on: on(n), hasCheck: true, trail: fragmentTokens(n) + ' tok', fragment: n }))
    }
    if (tab === 'abilities') {
      return ABILITIES.map((ab) => ({ id: ab.id, kind: 'ability', label: ab.name, on: on(ab.fragment), hasCheck: true, trail: ab.fragment, fragment: ab.fragment }))
    }
    return [
      ...SYSTEM_BASE.map((s) => ({ id: s.id, kind: 'system' as const, label: s.name, on: true, hasCheck: false, trail: s.tokens + ' tok', fragment: null })),
      ...fragments.map((n) => ({ id: 'sys-' + n, kind: 'system' as const, label: n, on: true, hasCheck: true, trail: fragmentTokens(n) + ' tok', fragment: n })),
    ]
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, allFragments, fragments])

  const counts = useMemo(() => {
    if (tab === 'fragments') return { active: fragments.length, total: allFragments.length }
    if (tab === 'abilities') return { active: ABILITIES.filter((a) => on(a.fragment)).length, total: ABILITIES.length }
    return { active: SYSTEM_BASE.length + fragments.length, total: SYSTEM_BASE.length + fragments.length }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, fragments, allFragments])

  const detail = useMemo<DrawerDetail | null>(() => drawer ? buildDetail(drawer, on) : null, [drawer, fragments])

  return (
    <div className={styles.grid}>
      <FragmentListPanel
        tab={tab}
        onTab={setTab}
        rows={rows}
        activeId={drawer?.id ?? null}
        activeCount={counts.active}
        totalCount={counts.total}
        onToggle={onToggleFragment}
        onInspect={(row) => inspect({ kind: row.kind, id: row.id })}
      />
      <div className={styles.rightCol}>
        <ComposedPromptView skill={skill} totalTokens={totalTokens} includedFragments={fragments} />
        <InspectDrawer detail={detail} onClose={closeDrawer} onToggle={onToggleFragment} />
      </div>
    </div>
  )
}

function buildDetail(target: { kind: string; id: string }, on: (n: string) => boolean): DrawerDetail {
  if (target.kind === 'ability') {
    const ab = ABILITIES.find((a) => a.id === target.id)!
    return {
      title: ab.name, kindLabel: 'Ability', desc: ab.desc, tokens: fragmentTokens(ab.fragment),
      source: ab.fragment, on: on(ab.fragment), canToggle: true, fragment: ab.fragment,
    }
  }
  if (target.kind === 'system') {
    const baseSeg = SYSTEM_BASE.find((s) => s.id === target.id)
    if (baseSeg) {
      return { title: baseSeg.name, kindLabel: 'System prompt', desc: baseSeg.desc, tokens: baseSeg.tokens, source: 'core directive', on: true, canToggle: false, fragment: null }
    }
    const fn = target.id.replace(/^sys-/, '')
    return { title: fn, kindLabel: 'System prompt', desc: fragmentPurpose(fn), tokens: fragmentTokens(fn), source: fn, on: on(fn), canToggle: true, fragment: fn }
  }
  const name = target.id
  return {
    title: name, kindLabel: 'Fragment', desc: FRAGMENT_META[name]?.purpose ?? '', tokens: fragmentTokens(name),
    source: name, on: on(name), canToggle: true, fragment: name,
  }
}
