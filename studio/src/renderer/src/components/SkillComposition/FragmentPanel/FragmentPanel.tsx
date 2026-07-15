import { Badge, Button } from '../../ui'
import type { SkillCompositionEntry } from '../../../services/skillComposition'
import { useFragmentToggles } from './hooks/useFragmentToggles'
import { useComposedPreview } from './hooks/useComposedPreview'
import { useChipSelection } from './hooks/useChipSelection'
import { useActiveChipContent } from './hooks/useActiveChipContent'
import { FragmentChipRow } from '../FragmentChipRow/FragmentChipRow'
import { ChipMarkdownView } from '../ChipMarkdownView/ChipMarkdownView'
import styles from './FragmentPanel.module.css'

interface Props {
  skill: string
  entry: SkillCompositionEntry | undefined
  allFragments: string[]
  projectRoot: string
  onChanged: () => void
}

export function FragmentPanel({ skill, entry, allFragments, projectRoot, onChanged }: Props): JSX.Element {
  const source = entry?.source ?? 'manifest'
  const { fragments, toggleFragment, resetToDefault, saving, resetting } = useFragmentToggles(
    skill,
    entry?.fragments ?? [],
    source,
    projectRoot,
    onChanged,
  )
  const { sections, loading: previewLoading } = useComposedPreview(skill, fragments, projectRoot)
  const { activeChipId, selectChip } = useChipSelection()
  const active = useActiveChipContent(skill, projectRoot, fragments, sections, previewLoading, activeChipId)

  const overridden = source === 'override'

  return (
    <div className={styles.root}>
      <div className={styles.header}>
        <span className={styles.skillName}>{skill}</span>
        {overridden && <Badge variant="integration" label="overridden" />}
        {saving && <span className={styles.status}>saving…</span>}
        <span className={styles.spacer} />
        <Button variant="ghost" size="sm" disabled={!overridden || resetting} onClick={resetToDefault}>
          {resetting ? 'Resetting…' : 'Reset to default'}
        </Button>
      </div>

      <FragmentChipRow
        fragments={fragments}
        allFragments={allFragments}
        activeChipId={activeChipId}
        onSelectChip={selectChip}
        onToggleFragment={toggleFragment}
      />

      <ChipMarkdownView title={active.title} sections={active.sections} loading={active.loading} />
    </div>
  )
}
