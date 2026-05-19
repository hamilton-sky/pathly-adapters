import { useState } from 'react'
import { ExternalLink, X as XIcon } from 'lucide-react'
import type { TerminalTab } from './types'
import styles from './Terminal.module.css'

interface PaneTabBarProps {
  pane: 'left' | 'right'
  tabs: TerminalTab[]
  activeTabId: string | null
  inline?: boolean
  onSelectTab: (id: string) => void
  onCloseTab: (id: string, e: React.MouseEvent) => void
  onAddTab: (pane: 'left' | 'right') => void
  onLaunch: (cmd: string | undefined, label: string, pane: 'left' | 'right') => void
  onPopout: (id: string) => void
  onRenameTab: (id: string, label: string) => void
}

export function PaneTabBar({
  pane, tabs, activeTabId, inline,
  onSelectTab, onCloseTab, onAddTab, onLaunch, onPopout, onRenameTab,
}: PaneTabBarProps): JSX.Element {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')

  const startEdit = (id: string, currentLabel: string, e: React.MouseEvent): void => {
    e.stopPropagation()
    setEditingId(id)
    setEditValue(currentLabel)
  }

  const commitEdit = (): void => {
    if (editingId && editValue.trim()) {
      onRenameTab(editingId, editValue.trim())
    }
    setEditingId(null)
  }

  const cancelEdit = (): void => setEditingId(null)

  return (
    <div className={inline ? styles.paneTabBarInline : styles.paneTabBar}>
      {tabs.map((tab) => (
        <div
          key={tab.id}
          onClick={() => onSelectTab(tab.id)}
          className={`${styles.tab} ${tab.id === activeTabId ? styles.tabActive : styles.tabInactive}`}
        >
          {editingId === tab.id ? (
            <input
              autoFocus
              className={styles.labelInput}
              title="Rename tab"
              aria-label="Rename tab"
              placeholder="Tab name"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onBlur={commitEdit}
              onKeyDown={(e) => {
                if (e.key === 'Enter') commitEdit()
                if (e.key === 'Escape') cancelEdit()
                e.stopPropagation()
              }}
              onClick={(e) => e.stopPropagation()}
            />
          ) : (
            <span onDoubleClick={(e) => startEdit(tab.id, tab.label, e)}>
              {tab.label}
            </span>
          )}
          <button
            title="Pop out to its own window"
            onClick={(e) => { e.stopPropagation(); onPopout(tab.id) }}
            className={styles.popoutBtn}
          >
            <ExternalLink size={10} />
          </button>
          <button
            title="Close tab"
            onClick={(e) => { e.stopPropagation(); onCloseTab(tab.id, e) }}
            className={styles.closeTabBtn}
          ><XIcon size={10} /></button>
        </div>
      ))}
      <div className={styles.actionGroup}>
        <button onClick={() => onAddTab(pane)} className={styles.iconBtn} title="New shell">+ Shell</button>
        <button
          onClick={() => onLaunch('claude', 'Claude', pane)}
          className={`${styles.iconBtn} ${styles.iconBtnClaude}`}
          title="Launch Claude Code"
        >Claude</button>
        <button
          onClick={() => onLaunch('codex', 'Codex', pane)}
          className={`${styles.iconBtn} ${styles.iconBtnCodex}`}
          title="Launch Codex"
        >Codex</button>
      </div>
    </div>
  )
}
