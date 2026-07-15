import { useState } from 'react'
import { Badge, Button, Tabs } from '../../ui'
import type { SkillCompositionEntry } from '../../../services/skillComposition'
import { useFragmentToggles } from './hooks/useFragmentToggles'
import { useComposedPreview } from './hooks/useComposedPreview'
import { useChipSelection } from './hooks/useChipSelection'
import { useActiveChipContent } from './hooks/useActiveChipContent'
import { FragmentChipRow } from '../FragmentChipRow/FragmentChipRow'
import { ChipMarkdownView } from '../ChipMarkdownView/ChipMarkdownView'
import { CompositionMapView } from '../CompositionMapView/CompositionMapView'
import styles from './FragmentPanel.module.css'

interface Props {
  skill: string
  entry: SkillCompositionEntry | undefined
  allFragments: string[]
  projectRoot: string
  onChanged: () => void
}

const VIEW_TABS = [
  { id: 'preview', label: 'Preview' },
  { id: 'config', label: 'Config' },
]

export function FragmentPanel({ skill, entry, allFragments, projectRoot, onChanged }: Props): JSX.Element {
  const source = entry?.source ?? 'manifest'
  const [view, setView] = useState<'preview' | 'config'>('config')
  const { fragments, toggleFragment, resetToDefault, saving, resetting } = useFragmentToggles(
    skill,
    entry?.fragments ?? [],
    source,
    projectRoot,
    onChanged,
  )
  const { sections, tokens, loading: previewLoading } = useComposedPreview(skill, fragments, projectRoot)
  const { activeChipId, selectChip } = useChipSelection()
  const active = useActiveChipContent(skill, projectRoot, sections, previewLoading, activeChipId)

  const overridden = source === 'override'

  function inspect(chipId: string): void {
    selectChip(chipId)
    setView('preview')
  }

  return (
    <div className={styles.root}>
      <div className={styles.header}>
        <div className={styles.titleRow}>
          <span className={styles.skillName}>{skill}</span>
          {overridden && <Badge variant="integration" label="overridden" />}
          {saving && <span className={styles.status}>saving…</span>}
          <span className={styles.spacer} />
          <Button variant="ghost" size="sm" disabled={!overridden || resetting} onClick={resetToDefault}>
            {resetting ? 'Resetting…' : 'Reset to default'}
          </Button>
        </div>
        <div className={styles.toolbar}>
          <Tabs tabs={VIEW_TABS} activeId={view} onChange={(id) => setView(id as 'preview' | 'config')} variant="pill" />
          <span className={styles.spacer} />
          <span className={styles.meta}>
            {fragments.length} fragment{fragments.length === 1 ? '' : 's'} · {source}
          </span>
        </div>
      </div>

      {view === 'config' ? (
        <CompositionMapView
          skill={skill}
          included={fragments}
          allFragments={allFragments}
          source={source}
          composedTokens={tokens}
          onToggleFragment={toggleFragment}
          onInspect={inspect}
        />
      ) : (
        <>
          <FragmentChipRow
            fragments={fragments}
            allFragments={allFragments}
            activeChipId={activeChipId}
            onSelectChip={selectChip}
            onToggleFragment={toggleFragment}
          />
          <ChipMarkdownView title={active.title} sections={active.sections} loading={active.loading} />
        </>
      )}
    </div>
  )
}
