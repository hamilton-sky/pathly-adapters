import { Database, Settings } from 'lucide-react'
import styles from '../Sidebar.module.css'

interface BottomNavProps {
  activePanel: string
  onMonitor: () => void
  onSettings: () => void
  onDbExplorer: () => void
}

export function BottomNav({ activePanel, onMonitor, onSettings, onDbExplorer }: BottomNavProps): JSX.Element {
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
        data-testid="sidebar-nav-db-explorer"
        className={`${styles.bottomRow} ${activePanel === 'db-explorer' ? styles.bottomRowActive : ''}`}
        onClick={onDbExplorer}
      >
        <Database size={15} />
        DB Explorer
      </button>

      <button
        type="button"
        data-testid="sidebar-nav-settings"
        className={`${styles.bottomRow} ${activePanel === 'settings' ? styles.bottomRowActive : ''}`}
        onClick={onSettings}
      >
        <Settings size={15} />
        Settings
      </button>

      <div className={styles.divider} />
    </>
  )
}
