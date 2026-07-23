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
      aria-selected={selected}
      onClick={() => onSelect(skillKey)}
    >
      <span className={styles.bar} />
      <span className={styles.label}>{label}</span>
      {overridden && <span className={styles.badge} title="Diverges from default">override</span>}
    </button>
  )
}
