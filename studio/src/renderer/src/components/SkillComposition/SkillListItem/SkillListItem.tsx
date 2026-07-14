import { Badge } from '../../ui'
import styles from './SkillListItem.module.css'

interface Props {
  skillKey: string
  overridden: boolean
  selected: boolean
  onSelect: (skill: string) => void
}

export function SkillListItem({ skillKey, overridden, selected, onSelect }: Props): JSX.Element {
  const label = skillKey.includes('/') ? skillKey.split('/').slice(1).join('/') : skillKey

  return (
    <button
      type="button"
      role="option"
      className={styles.item}
      data-selected={selected}
      onClick={() => onSelect(skillKey)}
      {...(selected ? { 'aria-selected': 'true' } : { 'aria-selected': 'false' })}
    >
      <span className={styles.label}>{label}</span>
      {overridden && (
        <Badge variant="integration" label="overridden" className={styles.badge} />
      )}
    </button>
  )
}
