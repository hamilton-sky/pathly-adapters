import { Database, Settings, MessageSquare, BookOpen, LayoutGrid } from 'lucide-react'
import styles from '../Sidebar.module.css'

interface BottomNavProps {
  activePanel: string
  onCommandCenter: () => void
  onMonitor: () => void
  onDbExplorer: () => void
  onMarkdownEditor: () => void
  onCanvas: () => void
  onSettings: () => void
}

/**
 * The PANELS nav — pinned at the foot of the sidebar (above the profile, outside the
 * scrolling tree) so it never scrolls away and is identical in the Workspace and Library tabs.
 * Single home for panel switching now that the header PanelNav is gone.
 */
export function BottomNav({
  activePanel,
  onCommandCenter,
  onMonitor,
  onDbExplorer,
  onMarkdownEditor,
  onCanvas,
  onSettings,
}: BottomNavProps): JSX.Element {
  return (
    <nav className={styles.panelsNav} aria-label="Panels">
      <div className={styles.panelsLabel}>Panels</div>

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
        data-testid="sidebar-nav-monitor"
        className={`${styles.bottomRow} ${activePanel === 'monitor' ? styles.bottomRowActive : ''}`}
        onClick={onMonitor}
      >
        <span className={styles.bottomIcon}><span className={styles.monitorDot} /></span>
        <span className={styles.bottomLabel}>Pipeline</span>
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
        data-testid="sidebar-nav-markdown-editor"
        className={`${styles.bottomRow} ${activePanel === 'markdown-editor' ? styles.bottomRowActive : ''}`}
        onClick={onMarkdownEditor}
      >
        <span className={styles.bottomIcon}><BookOpen size={15} strokeWidth={2} /></span>
        <span className={styles.bottomLabel}>Markdown Editor</span>
      </button>

      <button
        type="button"
        data-testid="sidebar-nav-canvas"
        className={`${styles.bottomRow} ${activePanel === 'flow' ? styles.bottomRowActive : ''}`}
        onClick={onCanvas}
      >
        <span className={styles.bottomIcon}><LayoutGrid size={15} strokeWidth={2} /></span>
        <span className={styles.bottomLabel}>Canvas</span>
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
    </nav>
  )
}
