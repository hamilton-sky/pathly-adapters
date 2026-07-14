import type { SkillCompositionEntry } from '../../../services/skillComposition'
import { SkillListItem } from '../SkillListItem/SkillListItem'
import styles from './SkillList.module.css'

interface Props {
  skills: Record<string, SkillCompositionEntry>
  selectedSkill: string | null
  onSelect: (skill: string) => void
  loading: boolean
}

function groupByCategory(skills: Record<string, SkillCompositionEntry>): Map<string, string[]> {
  const groups = new Map<string, string[]>()
  for (const key of Object.keys(skills).sort()) {
    const category = key.includes('/') ? key.split('/')[0] : 'other'
    const list = groups.get(category) ?? []
    list.push(key)
    groups.set(category, list)
  }
  return groups
}

export function SkillList({ skills, selectedSkill, onSelect, loading }: Props): JSX.Element {
  const groups = groupByCategory(skills)

  if (loading && groups.size === 0) {
    return <div className={styles.empty}>Loading skills…</div>
  }
  if (!loading && groups.size === 0) {
    return <div className={styles.empty}>No composable skills found</div>
  }

  return (
    <div className={styles.list} role="listbox" aria-label="Skills">
      {[...groups.entries()].map(([category, keys]) => (
        <div key={category} className={styles.group}>
          <div className={styles.groupLabel}>{category}</div>
          {keys.map((key) => (
            <SkillListItem
              key={key}
              skillKey={key}
              overridden={skills[key].source === 'override'}
              selected={key === selectedSkill}
              onSelect={onSelect}
            />
          ))}
        </div>
      ))}
    </div>
  )
}
