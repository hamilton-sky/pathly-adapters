import styles from './SectionLabel.module.css'

interface Props {
  label: string
  animDelay?: number
}

export function SectionLabel({ label, animDelay = 0 }: Props): JSX.Element {
  return (
    <span
      className={styles.label}
      style={{ '--anim-delay': `${animDelay}ms` } as React.CSSProperties}
    >
      {label}
    </span>
  )
}
