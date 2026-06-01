import { useState } from 'react'
import { ExternalLink, Trash2, X } from 'lucide-react'
import type { TerminalTab } from './types'
import { Tooltip } from '../ui'
import { TERMINAL_OPTIONS } from '../../lib/terminalOptions'
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
          <span className={styles.instanceNumericId}>#{tab.numericId}</span>
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
            type="button"
            title="Pop out to its own window"
            onClick={(e) => { e.stopPropagation(); onPopout(tab.id) }}
            className={styles.popoutBtn}
          >
            <ExternalLink size={10} />
          </button>
          <button
            type="button"
            title="Hide from full terminal"
            aria-label="Hide from full terminal"
            onClick={(e) => { e.stopPropagation(); onHideTab(tab.id, e) }}
            className={styles.hideTabBtn}
          ><X size={11} /></button>
          <button
            type="button"
            title="Kill terminal and close tab"
            aria-label="Kill terminal and close tab"
            onClick={(e) => { e.stopPropagation(); onCloseTab(tab.id, e) }}
            className={styles.closeTabBtn}
          ><Trash2 size={11} /></button>
        </div>
      ))}
      <div className={styles.actionGroup}>
        {TERMINAL_OPTIONS.map((opt) => {
          const tooltipProps = opt.kind === 'shell'
            ? { label: 'New shell tab', shortcut: 'Ctrl+Shift+S' }
            : opt.kind === 'claude'
            ? { label: 'Launch Claude Code', shortcut: 'Ctrl+Shift+C' }
            : opt.kind === 'codex'
            ? { label: 'Launch OpenAI Codex', shortcut: 'Ctrl+Shift+X' }
            : { label: `Launch ${opt.label}` }
          const kindClass = opt.kind !== 'shell'
            ? styles[`iconBtn${opt.kind.charAt(0).toUpperCase()}${opt.kind.slice(1)}`]
            : undefined
          return (
            <Tooltip key={opt.kind} {...tooltipProps} placement="top">
              <button
                type="button"
                onClick={() => opt.kind === 'shell' ? onAddTab(pane) : onLaunch(opt.command, opt.label, pane)}
                className={`${styles.iconBtn}${kindClass ? ` ${kindClass}` : ''}`}
              >
                {opt.icon(12)}
                {opt.kind === 'claude' ? 'Claude' : opt.label}
              </button>
            </Tooltip>
          )
        })}
      </div>
    </div>
  )
}
