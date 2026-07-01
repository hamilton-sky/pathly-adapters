import { Database, Settings, MessageSquare } from 'lucide-react'
import styles from '../Sidebar.module.css'

interface BottomNavProps {
  activePanel: string
  onMonitor: () => void
  onSettings: () => void
  onDbExplorer: () => void
  onCommandCenter: () => void
}

export function BottomNav({ activePanel, onMonitor, onSettings, onDbExplorer, onCommandCenter }: BottomNavProps): JSX.Element {
  return (
    <>
      <div className={styles.divider} />

      <button
        type="button"
        data-testid="sidebar-nav-monitor"
        className={`${styles.bottomRow} ${activePanel === 'monitor' ? styles.bottomRowActive : ''}`}
        onClick={onMonitor}
      >
        <span className={styles.bottomIcon}><span className={styles.monitorDot} /></span>
        <span className={styles.bottomLabel}>Monitor</span>
      </button>

      <button
        type="button"
        data-testid="sidebar-nav-command-center"
        className={`${styles.bottomRow} ${activePanel === 'command-center' ? styles.bottomRowActive : ''}`}
        onClick={onCommandCenter}
      >
        <span className={styles.bottomIcon}><MessageSquare size={15} strokeWidth={2} /></span>
        <span className={styles.bottomLabel}>Command Center</span>
      </button>

      <button
        type="button"
        data-testid="sidebar-nav-db-explorer"
        className={`${styles.bottomRow} ${activePanel === 'db-explorer' ? styles.bottomRowActive : ''}`}
        onClick={onDbExplorer}
      >
        <span className={styles.bottomIcon}><Database size={15} strokeWidth={2} /></span>
        <span className={styles.bottomLabel}>DB Explorer</span>
      </button>

      <button
        type="button"
        data-testid="sidebar-nav-settings"
        className={`${styles.bottomRow} ${activePanel === 'settings' ? styles.bottomRowActive : ''}`}
        onClick={onSettings}
      >
        <span className={styles.bottomIcon}><Settings size={15} strokeWidth={2} /></span>
        <span className={styles.bottomLabel}>Settings</span>
      </button>

      <div className={styles.divider} />
    </>
  )
}
