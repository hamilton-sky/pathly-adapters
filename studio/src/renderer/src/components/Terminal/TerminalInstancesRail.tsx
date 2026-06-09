import { useState } from 'react'
import { ChevronDown, ExternalLink, Menu, Trash2, X } from 'lucide-react'
import type { TerminalTab } from './types'
import { Tooltip } from '../ui'
import { ClaudeIcon, CodexIcon, ShellIcon } from './BrandIcons'
import styles from './Terminal.module.css'

interface TerminalInstancesRailProps {
  tabs: TerminalTab[]
  activeTabIds: Array<string | null>
  hiddenTabIds: Record<string, boolean>
  splitEnabled?: boolean
  onClosePanel: () => void
  onOpenTab: (id: string) => void
  onHideTab: (id: string) => void
  onKillTab: (id: string) => void
}

function TabBrandIcon({ kind }: { kind?: TerminalTab['kind'] }): JSX.Element | null {
  if (kind === 'shell' || !kind) return <ShellIcon size={15} />
  if (kind === 'claude') return <ClaudeIcon size={15} />
  if (kind === 'codex') return <CodexIcon size={15} />
  return null
}

function statusClass(status: TerminalTab['status']): string {
  if (status === 'running') return styles.statusRunning
  if (status === 'error') return styles.statusError
  if (status === 'done') return styles.statusDone
  return styles.statusIdle
}

interface TabRowProps {
  tab: TerminalTab
  active: boolean
  hidden: boolean
  onOpenTab: (id: string) => void
  onHideTab: (id: string) => void
  onKillTab: (id: string) => void
}

function TabRow({ tab, active, hidden, onOpenTab, onHideTab, onKillTab }: TabRowProps): JSX.Element {
  return (
    <div
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
        <span className={styles.instanceNumericId}>#{tab.numericId}</span>
        <span className={styles.instanceLabel}>{tab.label}</span>
      </button>
      <div className={styles.instanceActions}>
        <Tooltip label={hidden ? 'Show in terminal' : 'Focus terminal'} placement="left">
          <button
            type="button"
            className={styles.instanceActionBtn}
            onClick={() => onOpenTab(tab.id)}
            aria-label={hidden ? 'Show in terminal' : 'Focus terminal'}
          >
            <ExternalLink size={11} />
          </button>
        </Tooltip>
        <Tooltip label="Hide from full terminal" placement="left">
          <button
            type="button"
            className={styles.instanceActionBtn}
            onClick={() => onHideTab(tab.id)}
            aria-label="Hide from full terminal"
            disabled={hidden}
          >
            <X size={12} />
          </button>
        </Tooltip>
        <Tooltip label="Kill terminal and remove instance" placement="left">
          <button
            type="button"
            className={`${styles.instanceActionBtn} ${styles.instanceDangerBtn}`}
            onClick={() => onKillTab(tab.id)}
            aria-label="Kill terminal and remove instance"
          >
            <Trash2 size={12} />
          </button>
        </Tooltip>
      </div>
    </div>
  )
}

interface PlanGroupProps {
  plan: string
  stage?: string
  tabs: TerminalTab[]
  activeTabIds: Array<string | null>
  hiddenTabIds: Record<string, boolean>
  onOpenTab: (id: string) => void
  onHideTab: (id: string) => void
  onKillTab: (id: string) => void
}

function PlanGroup({ plan, stage, tabs, activeTabIds, hiddenTabIds, onOpenTab, onHideTab, onKillTab }: PlanGroupProps): JSX.Element {
  const [expanded, setExpanded] = useState(true)

  return (
    <div className={styles.treeGroup}>
      <button
        type="button"
        className={styles.treeGroupHeader}
        onClick={() => setExpanded((v) => !v)}
        {...(expanded ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
      >
        <ChevronDown
          size={11}
          className={`${styles.treeGroupChevron} ${expanded ? '' : styles.treeGroupChevronCollapsed}`}
        />
        <span className={styles.instanceLabel}>{plan}</span>
        {stage && <span className={styles.treeGroupBadge}>{stage}</span>}
      </button>
      {expanded && (
        <div className={styles.treeGroupItems}>
          {tabs.map((tab) => {
            const hidden = Boolean(hiddenTabIds[tab.id])
            const active = activeTabIds.includes(tab.id) && !hidden
            return (
              <TabRow
                key={tab.id}
                tab={tab}
                active={active}
                hidden={hidden}
                onOpenTab={onOpenTab}
                onHideTab={onHideTab}
                onKillTab={onKillTab}
              />
            )
          })}
        </div>
      )}
    </div>
  )
}

interface PaneGroupProps {
  label: string
  tabs: TerminalTab[]
  activeTabIds: Array<string | null>
  hiddenTabIds: Record<string, boolean>
  onOpenTab: (id: string) => void
  onHideTab: (id: string) => void
  onKillTab: (id: string) => void
}

function PaneGroup({ label, tabs: paneTabs, activeTabIds, hiddenTabIds, onOpenTab, onHideTab, onKillTab }: PaneGroupProps): JSX.Element {
  const [expanded, setExpanded] = useState(true)
  return (
    <div className={styles.treeGroup}>
      <button
        type="button"
        className={styles.treeGroupHeader}
        onClick={() => setExpanded((v) => !v)}
        {...(expanded ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
      >
        <ChevronDown
          size={11}
          className={`${styles.treeGroupChevron} ${expanded ? '' : styles.treeGroupChevronCollapsed}`}
        />
        <span className={styles.instanceLabel}>{label}</span>
        <span className={styles.treeGroupBadge}>{paneTabs.length}</span>
      </button>
      {expanded && (
        <div className={styles.treeGroupItems}>
          {paneTabs.map((tab) => {
            const hidden = Boolean(hiddenTabIds[tab.id])
            const active = activeTabIds.includes(tab.id) && !hidden
            return (
              <TabRow
                key={tab.id}
                tab={tab}
                active={active}
                hidden={hidden}
                onOpenTab={onOpenTab}
                onHideTab={onHideTab}
                onKillTab={onKillTab}
              />
            )
          })}
          {paneTabs.length === 0 && (
            <span className={styles.paneEmptyHint}>empty</span>
          )}
        </div>
      )}
    </div>
  )
}

export function TerminalInstancesRail({
  tabs,
  activeTabIds,
  hiddenTabIds,
  splitEnabled,
  onClosePanel,
  onOpenTab,
  onHideTab,
  onKillTab,
}: TerminalInstancesRailProps): JSX.Element {
  const hasAnyPlan = tabs.some((t) => t.plan)

  return (
    <aside className={styles.instancesRail} aria-label="Terminal instances">
      <div className={styles.instancesRailHeader}>
        <span>Instances</span>
        <Tooltip label="Close instances panel" placement="bottom">
          <button
            type="button"
            className={styles.instancesHeaderBtn}
            onClick={onClosePanel}
            aria-label="Close instances panel"
          >
            <Menu size={15} />
          </button>
        </Tooltip>
      </div>
      <div className={styles.instancesList}>
        {splitEnabled ? (
          <>
            <PaneGroup
              label="Left"
              tabs={tabs.filter((t) => t.pane === 'left')}
              activeTabIds={activeTabIds}
              hiddenTabIds={hiddenTabIds}
              onOpenTab={onOpenTab}
              onHideTab={onHideTab}
              onKillTab={onKillTab}
            />
            <PaneGroup
              label="Right"
              tabs={tabs.filter((t) => t.pane === 'right')}
              activeTabIds={activeTabIds}
              hiddenTabIds={hiddenTabIds}
              onOpenTab={onOpenTab}
              onHideTab={onHideTab}
              onKillTab={onKillTab}
            />
          </>
        ) : !hasAnyPlan ? (
          // Backwards-compatible flat list when no tab has a plan
          tabs.map((tab) => {
            const hidden = Boolean(hiddenTabIds[tab.id])
            const active = activeTabIds.includes(tab.id) && !hidden
            return (
              <TabRow
                key={tab.id}
                tab={tab}
                active={active}
                hidden={hidden}
                onOpenTab={onOpenTab}
                onHideTab={onHideTab}
                onKillTab={onKillTab}
              />
            )
          })
        ) : (
          // Tree grouped by plan
          (() => {
            // Build ordered groups preserving first-seen order
            const groupOrder: string[] = []
            const groupMap: Record<string, { stage?: string; tabs: TerminalTab[] }> = {}

            for (const tab of tabs) {
              const key = tab.plan ?? '__free__'
              if (!groupMap[key]) {
                groupOrder.push(key)
                groupMap[key] = { stage: tab.stage, tabs: [] }
              }
              groupMap[key].tabs.push(tab)
            }

            // Sort: named plans first, "Free" last
            const sortedKeys = [
              ...groupOrder.filter((k) => k !== '__free__'),
              ...groupOrder.filter((k) => k === '__free__'),
            ]

            return sortedKeys.map((key) => {
              const group = groupMap[key]
              if (key === '__free__') {
                return (
                  <PlanGroup
                    key="__free__"
                    plan="Free"
                    tabs={group.tabs}
                    activeTabIds={activeTabIds}
                    hiddenTabIds={hiddenTabIds}
                    onOpenTab={onOpenTab}
                    onHideTab={onHideTab}
                    onKillTab={onKillTab}
                  />
                )
              }
              return (
                <PlanGroup
                  key={key}
                  plan={key}
                  stage={group.stage}
                  tabs={group.tabs}
                  activeTabIds={activeTabIds}
                  hiddenTabIds={hiddenTabIds}
                  onOpenTab={onOpenTab}
                  onHideTab={onHideTab}
                  onKillTab={onKillTab}
                />
              )
            })
          })()
        )}
      </div>
    </aside>
  )
}
