import React from 'react'
import { GripHorizontal, X } from 'lucide-react'
import { useUiStore } from '../../store/uiStore'
import { useTerminalStore } from '../../store/terminalStore'
import { fmtElapsed } from '../shared/RunPill/progress'
import { adapterLabel } from '../../services/cliEngine'
import type { CliAdapter } from '../../services/cliEngine'
import { useCliMonitor } from './useCliMonitor'
import type { CliSession, SessionRecord } from './useCliMonitor'
import { SpawnQueuePanel } from './SpawnQueuePanel'
import s from './CliMonitorBar.module.css'

function fmtAgo(ms: number): string {
  const secs = Math.floor((Date.now() - ms) / 1000)
  if (secs < 60) return `${secs}s ago`
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`
  return `${Math.floor(secs / 3600)}h ago`
}

function SessionRow({ session, expanded, onToggle }: { session: CliSession; expanded: boolean; onToggle: () => void }): JSX.Element {
  const { tab, elapsedS, lastLines } = session
  const adapter = (tab.kind ?? 'claude') as CliAdapter
  const handleStop = () => { void window.pathly.terminal.kill(tab.id) }
  const handleOpen = () => { useTerminalStore.getState().openTab(tab.id) }

  return (
    <div className={s.rowGroup}>
      <button type="button" className={s.row} onClick={onToggle} aria-expanded={expanded ? 'true' : 'false'}>
        <span className={s.badge} data-adapter={adapter}>{adapterLabel(adapter)}</span>
        <span className={s.rowLabel}>{tab.label}</span>
        <span className={s.elapsed}>{fmtElapsed(elapsedS)}</span>
        <span
          role="button"
          tabIndex={0}
          className={s.stopBtn}
          onClick={(e) => { e.stopPropagation(); handleStop() }}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.stopPropagation(); handleStop() } }}
          aria-label="Stop engine"
        >
          &#9632;
        </span>
      </button>
      {expanded && (
        <div className={s.expanded}>
          {lastLines.length > 0 && (
            <div className={s.outputLines}>
              {lastLines.map((l, i) => <div key={i}>{l}</div>)}
            </div>
          )}
          {tab.prompt && (
            <div className={s.promptSnippet}>{tab.prompt.slice(0, 120)}{tab.prompt.length > 120 ? '…' : ''}</div>
          )}
          <button type="button" className={s.openTermBtn} onClick={handleOpen}>&#8599; open terminal</button>
        </div>
      )}
    </div>
  )
}

function HistoryRow({ record, expanded, onToggle }: { record: SessionRecord; expanded: boolean; onToggle: () => void }): JSX.Element {
  const adapter = (record.kind ?? 'claude') as CliAdapter
  return (
    <div className={s.rowGroup}>
      <button type="button" className={s.historyRow} onClick={onToggle} aria-expanded={expanded ? 'true' : 'false'}>
        <span className={s.historyStatus} data-status={record.status}>{record.status === 'done' ? '✓' : '✗'}</span>
        <span className={s.badge} data-adapter={adapter}>{adapterLabel(adapter)}</span>
        <span className={s.rowLabel}>{record.label}</span>
        <span className={s.timeAgo}>{fmtAgo(record.finishedAt)}</span>
      </button>
      {expanded && (
        <div className={s.expanded}>
          {record.lastLines.length > 0 && (
            <div className={s.outputLines}>
              {record.lastLines.map((l, i) => <div key={i}>{l}</div>)}
            </div>
          )}
          {record.prompt && (
            <div className={s.promptSnippet}>{record.prompt.slice(0, 120)}{record.prompt.length > 120 ? '…' : ''}</div>
          )}
        </div>
      )}
    </div>
  )
}

export function CliMonitorBar(): JSX.Element | null {
  const open = useUiStore((s) => s.cliMonitorOpen)
  const toggleCliMonitor = useUiStore((s) => s.toggleCliMonitor)
  const { sessions, history, spawnQueue, pos, onDragStart, expandedIds, toggleExpand } = useCliMonitor()

  if (!open) return null

  const rateLimited = spawnQueue.rateLimitedUntil > Date.now()

  return (
    <div
      className={s.bar}
      style={{ '--bar-x': `${pos.x}px`, '--bar-y': `${pos.y}px` } as React.CSSProperties}
    >
      <div className={s.header} onMouseDown={onDragStart} role="toolbar" aria-label="CLI Engines">
        <GripHorizontal size={12} className={s.grip} aria-hidden="true" />
        <span className={s.title}>CLI Engines</span>
        <span className={s.activeCount}>{spawnQueue.total}/{spawnQueue.caps.global}</span>
        {spawnQueue.queued.length > 0 && (
          <span className={s.queuedCount}>{spawnQueue.queued.length} queued</span>
        )}
        {spawnQueue.paused && <span className={s.pausedBadge}>paused</span>}
        <button type="button" className={s.closeBtn} onClick={toggleCliMonitor} aria-label="Close CLI monitor">
          <X size={12} />
        </button>
      </div>

      <div className={s.body}>
        {rateLimited && (
          <div className={s.rateLimitBanner}>Rate-limited — backing off, runs are queued</div>
        )}
        <SpawnQueuePanel spawnQueue={spawnQueue} />
        {sessions.length === 0 && history.length === 0 && !rateLimited && spawnQueue.queued.length === 0 && (
          <p className={s.empty}>No active engines</p>
        )}
        {sessions.length > 0 && (
          <>
            <div className={s.sectionLabel}>ACTIVE</div>
            {sessions.map((session) => (
              <SessionRow key={session.tab.id} session={session} expanded={expandedIds.has(session.tab.id)} onToggle={() => toggleExpand(session.tab.id)} />
            ))}
          </>
        )}
        {history.length > 0 && (
          <>
            <div className={s.sectionLabel}>RECENT</div>
            {history.map((record) => (
              <HistoryRow key={`${record.id}-${record.finishedAt}`} record={record} expanded={expandedIds.has(record.id)} onToggle={() => toggleExpand(record.id)} />
            ))}
          </>
        )}
      </div>
    </div>
  )
}
