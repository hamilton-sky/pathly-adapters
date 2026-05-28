import { ExternalLink, Menu, Trash2, X } from 'lucide-react'
import type { TerminalTab } from './types'
import { ClaudeIcon, CodexIcon, ShellIcon } from './BrandIcons'
import styles from './Terminal.module.css'

interface TerminalInstancesRailProps {
  tabs: TerminalTab[]
  activeTabIds: Array<string | null>
  hiddenTabIds: Record<string, boolean>
  onClosePanel: () => void
  onOpenTab: (id: string) => void
  onHideTab: (id: string) => void
  onKillTab: (id: string) => void
}

function TabBrandIcon({ kind }: { kind?: TerminalTab['kind'] }): JSX.Element | null {
  if (kind === 'shell' || !kind) return <ShellIcon size={13} />
  if (kind === 'claude') return <ClaudeIcon size={13} />
  if (kind === 'codex') return <CodexIcon size={13} />
  return null
}

function statusClass(status: TerminalTab['status']): string {
  if (status === 'running') return styles.statusRunning
  if (status === 'error') return styles.statusError
  if (status === 'done') return styles.statusDone
  return styles.statusIdle
}

export function TerminalInstancesRail({
  tabs,
  activeTabIds,
  hiddenTabIds,
  onClosePanel,
  onOpenTab,
  onHideTab,
  onKillTab,
}: TerminalInstancesRailProps): JSX.Element {
  return (
    <aside className={styles.instancesRail} aria-label="Terminal instances">
      <div className={styles.instancesRailHeader}>
        <span>Instances</span>
        <button
          type="button"
          className={styles.instancesHeaderBtn}
          onClick={onClosePanel}
          title="Close instances panel"
          aria-label="Close instances panel"
        >
          <Menu size={13} />
        </button>
      </div>
      <div className={styles.instancesList}>
        {tabs.map((tab) => {
          const hidden = Boolean(hiddenTabIds[tab.id])
          const active = activeTabIds.includes(tab.id) && !hidden
          return (
            <div
              key={tab.id}
              className={`${styles.instanceItem} ${active ? styles.instanceItemActive : ''} ${hidden ? styles.instanceItemHidden : ''}`}
            >
              <button
                type="button"
                className={styles.instanceMain}
                onClick={() => onOpenTab(tab.id)}
                title={hidden ? `Show ${tab.label}` : `Focus ${tab.label}`}
              >
                <span className={`${styles.statusDot} ${statusClass(tab.status)}`} />
                <TabBrandIcon kind={tab.kind} />
                <span className={styles.instanceLabel}>{tab.label}</span>
              </button>
              <div className={styles.instanceActions}>
                <button
                  type="button"
                  className={styles.instanceActionBtn}
                  onClick={() => onOpenTab(tab.id)}
                  title={hidden ? 'Show in terminal' : 'Focus terminal'}
                  aria-label={hidden ? 'Show in terminal' : 'Focus terminal'}
                >
                  <ExternalLink size={11} />
                </button>
                <button
                  type="button"
                  className={styles.instanceActionBtn}
                  onClick={() => onHideTab(tab.id)}
                  title="Hide from full terminal"
                  aria-label="Hide from full terminal"
                  disabled={hidden}
                >
                  <X size={12} />
                </button>
                <button
                  type="button"
                  className={`${styles.instanceActionBtn} ${styles.instanceDangerBtn}`}
                  onClick={() => onKillTab(tab.id)}
                  title="Kill terminal and remove instance"
                  aria-label="Kill terminal and remove instance"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </aside>
  )
}
