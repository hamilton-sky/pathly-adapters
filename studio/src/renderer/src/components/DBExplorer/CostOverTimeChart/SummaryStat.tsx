import styles from './SummaryStat.module.css'

interface SummaryStatProps {
  value: string
  label: string
  tone?: 'default' | 'green' | 'teal'
}

/** One "big number + caption" cell used in the chart header. */
export function SummaryStat({ value, label, tone = 'default' }: SummaryStatProps): JSX.Element {
  return (
    <div className={styles.stat}>
      <span className={styles.value} {...(tone !== 'default' ? { 'data-tone': tone } : {})}>
        {value}
      </span>
      <span className={styles.label}>{label}</span>
    </div>
  )
}
