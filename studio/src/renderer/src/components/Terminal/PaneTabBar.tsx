import { useState } from 'react'
import { ExternalLink, Trash2, X } from 'lucide-react'
import type { TerminalTab } from './types'
import { Tooltip } from '../ui'
import { TERMINAL_OPTIONS } from '../../lib/terminalOptions'
import { SplitLauncher } from './SplitLauncher'
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
  const opt = TERMINAL_OPTIONS.find((o) => o.kind === (kind ?? 'shell'))
  return opt ? opt.icon(13) : null
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
          className={`${styles.tab} ${tab.id === activeTabId ? styles.tabActive : styles.tabInactive}${tab.runnerOwned ? ` ${styles.tabRunner}` : ''}`}
        >
          <Tooltip label={`${tab.label} #${tab.numericId}`} delay={400} placement="bottom">
            <button
              type="button"
              className={styles.tabIconArea}
              onClick={() => onSelectTab(tab.id)}
              onDoubleClick={(e) => startEdit(tab.id, tab.label, e)}
              aria-label={`Select tab: ${tab.label}`}
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
            </button>
          </Tooltip>
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
          ) : null}
          <div className={styles.tabActions}>
            <Tooltip label="Pop out to its own window" placement="bottom">
              <button
                type="button"
                aria-label="Pop out to its own window"
                onClick={(e) => { e.stopPropagation(); onPopout(tab.id) }}
                className={styles.popoutBtn}
              >
                <ExternalLink size={10} />
              </button>
            </Tooltip>
            <Tooltip label="Hide from full terminal" placement="bottom">
              <button
                type="button"
                aria-label="Hide from full terminal"
                onClick={(e) => { e.stopPropagation(); onHideTab(tab.id, e) }}
                className={styles.hideTabBtn}
              >
                <X size={11} />
              </button>
            </Tooltip>
            <Tooltip label="Kill terminal and close tab" placement="bottom">
              <button
                type="button"
                aria-label="Kill terminal and close tab"
                onClick={(e) => { e.stopPropagation(); onCloseTab(tab.id, e) }}
                className={styles.closeTabBtn}
              >
                <Trash2 size={11} />
              </button>
            </Tooltip>
          </div>
        </div>
      ))}
      <SplitLauncher pane={pane} onAddTab={onAddTab} onLaunch={onLaunch} />
    </div>
  )
}
