import styles from './Separator.module.css'

interface SeparatorProps {
  label?: string
}

function Separator({ label }: SeparatorProps): JSX.Element {
  if (!label) {
    return <div className={styles.bare} />
  }

  return (
    <div className={styles.labeled}>
      <div className={styles.line} />
      <span className={styles.text}>{label}</span>
      <div className={styles.line} />
    </div>
  )
}
