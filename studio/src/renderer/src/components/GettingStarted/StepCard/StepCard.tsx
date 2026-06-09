import styles from './StepCard.module.css'

interface Props {
  step: string
  title: string
  desc: string
  index: number
}

export function StepCard({ step, title, desc, index }: Props): JSX.Element {
  return (
    <div className={styles.card} data-index={index}>
      <div className={styles.badge}>
        <span className={styles.badgeNum}>{step}</span>
      </div>
      <div className={styles.content}>
        <p className={styles.title}>{title}</p>
        <p className={styles.desc}>{desc}</p>
      </div>
    </div>
  )
}
