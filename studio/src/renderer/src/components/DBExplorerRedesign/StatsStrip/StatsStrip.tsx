import type { TopStat } from '../types'
import styles from './StatsStrip.module.css'

interface StatsStripProps {
  stats: TopStat[]
}

/** The five aggregate counters across the top of the panel. */
export function StatsStrip({ stats }: StatsStripProps): JSX.Element {
  return (
    <div className={styles.stats}>
      {stats.map((s) => (
        <div key={s.k} className={styles.stat}>
          <div className={styles.k}>{s.k}</div>
          <div className={`${styles.v} ${s.cost ? styles.cost : ''}`}>{s.v}</div>
        </div>
      ))}
    </div>
  )
}
