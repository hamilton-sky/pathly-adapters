import { BookOpen, Layers, Activity, Database, Settings, PanelLeft, MessageSquare, FileText, LayoutGrid } from 'lucide-react'
import { useBrightskyStore } from '../../../store/brightskyStore'
import { Tooltip } from '../../ui'
import styles from './IconStrip.module.css'

interface IconStripProps {
  activePanel: string
  libraryOpen: boolean
  onExpand: () => void
  onWorkspace: () => void
  onLibrary: () => void
  onCommandCenter: () => void
  onMonitor: () => void
  onDbExplorer: () => void
  onMarkdownEditor: () => void
  onCanvas: () => void
  onSettings: () => void
}

export function IconStrip({
  activePanel,
  libraryOpen,
  onExpand,
  onWorkspace,
  onLibrary,
  onCommandCenter,
  onMonitor,
  onDbExplorer,
  onMarkdownEditor,
  onCanvas,
  onSettings,
}: IconStripProps): JSX.Element {
  const displayName = useBrightskyStore((s) => s.userDisplayName)
  const initials = displayName
    ? displayName.split(' ').map((w) => w[0] ?? '').slice(0, 2).join('').toUpperCase()
    : null

  return (
    <aside className={styles.strip} aria-label="Collapsed sidebar">
      <Tooltip label="Expand sidebar" placement="right">
        <button type="button" className={styles.expandBtn} onClick={onExpand} aria-label="Expand sidebar">
          <PanelLeft size={15} />
        </button>
      </Tooltip>

      <div className={styles.divider} />

      <Tooltip label="Workspace" placement="right">
        <button
          type="button"
          className={`${styles.iconBtn} ${!libraryOpen ? styles.iconBtnActive : ''}`}
          onClick={onWorkspace}
          aria-label="Workspace"
        >
          <Layers size={16} />
        </button>
      </Tooltip>

      <Tooltip label="Library" placement="right">
        <button
          type="button"
          className={`${styles.iconBtn} ${libraryOpen ? styles.iconBtnActive : ''}`}
          onClick={onLibrary}
          aria-label="Library"
        >
          <BookOpen size={16} />
        </button>
      </Tooltip>

      <div className={styles.spacer} />

      <Tooltip label="Command Center" placement="right">
        <button
          type="button"
          className={`${styles.iconBtn} ${activePanel === 'command-center' ? styles.iconBtnActive : ''}`}
          onClick={onCommandCenter}
          aria-label="Command Center"
        >
          <MessageSquare size={16} />
        </button>
      </Tooltip>

      <Tooltip label="Monitor" placement="right">
        <button
          type="button"
          className={`${styles.iconBtn} ${activePanel === 'monitor' ? styles.iconBtnActive : ''}`}
          onClick={onMonitor}
          aria-label="Monitor"
        >
          <Activity size={16} />
        </button>
      </Tooltip>

      <Tooltip label="DB Explorer" placement="right">
        <button
          type="button"
          className={`${styles.iconBtn} ${activePanel === 'db-explorer' ? styles.iconBtnActive : ''}`}
          onClick={onDbExplorer}
          aria-label="DB Explorer"
        >
          <Database size={16} />
        </button>
      </Tooltip>

      <Tooltip label="Markdown Editor" placement="right">
        <button
          type="button"
          className={`${styles.iconBtn} ${activePanel === 'markdown-editor' ? styles.iconBtnActive : ''}`}
          onClick={onMarkdownEditor}
          aria-label="Markdown Editor"
        >
          <FileText size={16} />
        </button>
      </Tooltip>

      <Tooltip label="Canvas" placement="right">
        <button
          type="button"
          className={`${styles.iconBtn} ${activePanel === 'flow' ? styles.iconBtnActive : ''}`}
          onClick={onCanvas}
          aria-label="Canvas"
        >
          <LayoutGrid size={16} />
        </button>
      </Tooltip>

      <Tooltip label="Settings" placement="right">
        <button
          type="button"
          className={`${styles.iconBtn} ${activePanel === 'settings' ? styles.iconBtnActive : ''}`}
          onClick={onSettings}
          aria-label="Settings"
        >
          <Settings size={16} />
        </button>
      </Tooltip>

      <div className={styles.divider} />

      {initials && (
        <Tooltip label="Profile" placement="right">
          <div className={styles.avatar} aria-label="Profile">
            {initials}
          </div>
        </Tooltip>
      )}
    </aside>
  )
}
