import styles from '../Sidebar.module.css'

interface BottomNavProps {
  activePanel: string
  onMonitor: () => void
  onSettings: () => void
}

export function BottomNav({ activePanel, onMonitor, onSettings }: BottomNavProps): JSX.Element {
  return (
    <>
      <div className={styles.divider} />

      <button
        type="button"
        data-testid="sidebar-nav-monitor"
        className={`${styles.bottomRow} ${activePanel === 'monitor' ? styles.bottomRowActive : ''}`}
        onClick={onMonitor}
      >
        <span className={styles.monitorDot}>●</span> Monitor
      </button>

      <button
        type="button"
        data-testid="sidebar-nav-settings"
        className={`${styles.bottomRow} ${activePanel === 'settings' ? styles.bottomRowActive : ''}`}
        onClick={onSettings}
      >
        ⚙ Settings
      </button>

      <div className={styles.divider} />
    </>
  )
}
