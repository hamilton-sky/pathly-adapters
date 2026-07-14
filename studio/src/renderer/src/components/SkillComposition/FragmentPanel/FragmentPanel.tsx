import { Badge, Button } from '../../ui'
import type { SkillCompositionEntry } from '../../../services/skillComposition'
import { useFragmentToggles } from './hooks/useFragmentToggles'
import { useComposedPreview } from './hooks/useComposedPreview'
import { FragmentToggleRow } from '../FragmentToggleRow/FragmentToggleRow'
import { ComposedPreview } from '../ComposedPreview/ComposedPreview'
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
  const { sections, tokens, loading: previewLoading } = useComposedPreview(skill, fragments, projectRoot)

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

      <div className={styles.toggles}>
        {allFragments.map((name) => (
          <FragmentToggleRow key={name} name={name} checked={fragments.includes(name)} onToggle={toggleFragment} />
        ))}
        {allFragments.length === 0 && <div className={styles.emptyToggles}>No fragments found</div>}
      </div>

      <ComposedPreview sections={sections} tokens={tokens} loading={previewLoading} />
    </div>
  )
}
