import { useState } from 'react'
import { ExternalLink, Trash2, X } from 'lucide-react'
import type { TerminalTab } from './types'
import { Tooltip } from '../ui'
import { ClaudeIcon, CodexIcon, ShellIcon } from './BrandIcons'
import styles from './Terminal.module.css'

interface PaneTabBarProps {
  pane: 'left' | 'right'
  tabs: TerminalTab[]
  activeTabId: string | null
  inline?: boolean
  onSelectTab: (id: string) => void
  onCloseTab: (id: string, e: React.MouseEvent) => void
  onHideTab: (id: string, e: React.MouseEvent) => void
  onAddTab: (pane: 'left' | 'right') => void
  onLaunch: (cmd: string | undefined, label: string, pane: 'left' | 'right') => void
  onPopout: (id: string) => void
  onRenameTab: (id: string, label: string) => void
}

function TabBrandIcon({ kind }: { kind?: TerminalTab['kind'] }): JSX.Element | null {
  if (kind === 'shell' || !kind) return <ShellIcon size={13} />
  if (kind === 'claude') return <ClaudeIcon size={13} />
  if (kind === 'codex')  return <CodexIcon  size={13} />
  return null
}

export function PaneTabBar({
  pane, tabs, activeTabId, inline,
  onSelectTab, onCloseTab, onHideTab, onAddTab, onLaunch, onPopout, onRenameTab,
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
          <span
            className={`${styles.statusDot} ${
              tab.status === 'running' ? styles.statusRunning :
              tab.status === 'error'   ? styles.statusError :
              tab.status === 'done'    ? styles.statusDone :
              styles.statusIdle
            }`}
            aria-label={`Status: ${tab.status ?? 'idle'}`}
          />
          <TabBrandIcon kind={tab.kind} />
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
            title="Hide from full terminal"
            aria-label="Hide from full terminal"
            onClick={(e) => { e.stopPropagation(); onHideTab(tab.id, e) }}
            className={styles.hideTabBtn}
          ><X size={11} /></button>
          <button
            title="Kill terminal and close tab"
            aria-label="Kill terminal and close tab"
            onClick={(e) => { e.stopPropagation(); onCloseTab(tab.id, e) }}
            className={styles.closeTabBtn}
          ><Trash2 size={11} /></button>
        </div>
      ))}
      <div className={styles.actionGroup}>
        <Tooltip label="New shell tab" shortcut="Ctrl+Shift+S" placement="top">
          <button onClick={() => onAddTab(pane)} className={styles.iconBtn}>
            <ShellIcon size={12} />
            Shell
          </button>
        </Tooltip>
        <Tooltip label="Launch Claude Code" shortcut="Ctrl+Shift+C" placement="top">
          <button
            onClick={() => onLaunch('claude', 'Claude', pane)}
            className={`${styles.iconBtn} ${styles.iconBtnClaude}`}
          >
            <ClaudeIcon size={12} />
            Claude
          </button>
        </Tooltip>
        <Tooltip label="Launch OpenAI Codex" shortcut="Ctrl+Shift+X" placement="top">
          <button
            onClick={() => onLaunch('codex', 'Codex', pane)}
            className={`${styles.iconBtn} ${styles.iconBtnCodex}`}
          >
            <CodexIcon size={12} />
            Codex
          </button>
        </Tooltip>
      </div>
    </div>
  )
}
