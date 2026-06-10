import { BookOpen, Layers, Activity, Database, Settings, ChevronRight } from 'lucide-react'
import { useBrightskyStore } from '../../../store/brightskyStore'
import styles from './IconStrip.module.css'

interface IconStripProps {
  activePanel: string
  libraryOpen: boolean
  onExpand: () => void
  onWorkspace: () => void
  onLibrary: () => void
  onMonitor: () => void
  onDbExplorer: () => void
  onSettings: () => void
}

export function IconStrip({
  activePanel,
  libraryOpen,
  onExpand,
  onWorkspace,
  onLibrary,
  onMonitor,
  onDbExplorer,
  onSettings,
}: IconStripProps): JSX.Element {
  const displayName = useBrightskyStore((s) => s.userDisplayName)
  const initials = displayName
    ? displayName.split(' ').map((w) => w[0] ?? '').slice(0, 2).join('').toUpperCase()
    : null

  return (
    <aside className={styles.strip} aria-label="Collapsed sidebar">
      <button type="button" className={styles.expandBtn} onClick={onExpand} title="Expand sidebar" aria-label="Expand sidebar">
        <ChevronRight size={14} />
      </button>

      <div className={styles.divider} />

      <button
        type="button"
        className={`${styles.iconBtn} ${!libraryOpen ? styles.iconBtnActive : ''}`}
        onClick={onWorkspace}
        title="Workspace"
        aria-label="Workspace"
      >
        <Layers size={16} />
      </button>

      <button
        type="button"
        className={`${styles.iconBtn} ${libraryOpen ? styles.iconBtnActive : ''}`}
        onClick={onLibrary}
        title="Library"
        aria-label="Library"
      >
        <BookOpen size={16} />
      </button>

      <div className={styles.spacer} />

      <button
        type="button"
        className={`${styles.iconBtn} ${activePanel === 'monitor' ? styles.iconBtnActive : ''}`}
        onClick={onMonitor}
        title="Monitor"
        aria-label="Monitor"
      >
        <Activity size={16} />
      </button>

      <button
        type="button"
        className={`${styles.iconBtn} ${activePanel === 'db-explorer' ? styles.iconBtnActive : ''}`}
        onClick={onDbExplorer}
        title="DB Explorer"
        aria-label="DB Explorer"
      >
        <Database size={16} />
      </button>

      <button
        type="button"
        className={`${styles.iconBtn} ${activePanel === 'settings' ? styles.iconBtnActive : ''}`}
        onClick={onSettings}
        title="Settings"
        aria-label="Settings"
      >
        <Settings size={16} />
      </button>

      <div className={styles.divider} />

      {initials && (
        <div className={styles.avatar} title="Profile">
          {initials}
        </div>
      )}
    </aside>
  )
}
