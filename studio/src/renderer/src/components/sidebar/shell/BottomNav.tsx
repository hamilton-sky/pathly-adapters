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
        <span className={styles.monitorDot}>●</span> Monitor
      </button>

      <button
        type="button"
        data-testid="sidebar-nav-command-center"
        className={`${styles.bottomRow} ${activePanel === 'command-center' ? styles.bottomRowActive : ''}`}
        onClick={onCommandCenter}
      >
        <MessageSquare size={15} />
        Command Center
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
