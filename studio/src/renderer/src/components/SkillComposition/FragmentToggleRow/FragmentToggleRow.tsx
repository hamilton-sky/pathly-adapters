import styles from './FragmentToggleRow.module.css'

interface Props {
  name: string
  checked: boolean
  onToggle: (name: string) => void
}

export function FragmentToggleRow({ name, checked, onToggle }: Props): JSX.Element {
  return (
    <label className={styles.row} data-checked={checked}>
      <input
        type="checkbox"
        className={styles.checkbox}
        checked={checked}
        onChange={() => onToggle(name)}
        aria-label={`Toggle fragment ${name}`}
      />
      <span className={styles.name}>{name}</span>
    </label>
  )
}
