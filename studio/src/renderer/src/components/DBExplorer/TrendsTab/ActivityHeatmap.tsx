import type { HeatmapCell } from './useTrends'
import styles from './TrendsTab.module.css'

interface ActivityHeatmapProps {
  cells: HeatmapCell[]
}

export function ActivityHeatmap({ cells }: ActivityHeatmapProps): JSX.Element {
  return (
    <div className={styles.heatmapGrid}>
      {cells.map((cell) => (
        <div
          key={cell.date}
          className={styles.heatmapCell}
          data-level={cell.level}
          title={`${cell.date}: ${cell.count} runs`}
        />
      ))}
    </div>
  )
}
