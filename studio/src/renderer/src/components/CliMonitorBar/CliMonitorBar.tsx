import { GripHorizontal, Square, X } from 'lucide-react'
import { useUiStore } from '../../store/uiStore'
import { fmtElapsed } from '../shared/RunPill/progress'
import { adapterLabel } from '../../services/cliEngine'
import type { CliAdapter } from '../../services/cliEngine'
import { useCliMonitor } from './useCliMonitor'
import type { CliSession } from './useCliMonitor'
import s from './CliMonitorBar.module.css'

function SessionRow({ session }: { session: CliSession }): JSX.Element {
  const { tab, elapsedS } = session
  const adapter = (tab.kind ?? 'claude') as CliAdapter

  const handleStop = () => { void window.pathly.terminal.kill(tab.id) }

  return (
    <div className={s.row}>
      <span className={s.badge} data-adapter={adapter}>
        {adapterLabel(adapter)}
      </span>
      <span className={s.rowLabel}>{tab.label}</span>
      <span className={s.elapsed}>{fmtElapsed(elapsedS)}</span>
      <button type="button" className={s.stopBtn} onClick={handleStop} aria-label="Stop engine">
        <Square size={9} />
      </button>
    </div>
  )
}

export function CliMonitorBar(): JSX.Element | null {
  const open = useUiStore((s) => s.cliMonitorOpen)
  const toggleCliMonitor = useUiStore((s) => s.toggleCliMonitor)
  const { sessions, pos, onDragStart } = useCliMonitor()

  if (!open) return null

  return (
    <div
      className={s.bar}
      style={{ '--bar-x': `${pos.x}px`, '--bar-y': `${pos.y}px` } as React.CSSProperties}
    >
      <div className={s.header} onMouseDown={onDragStart} role="toolbar" aria-label="CLI Engines">
        <GripHorizontal size={12} className={s.grip} aria-hidden="true" />
        <span className={s.title}>CLI Engines</span>
        {sessions.length > 0 && (
          <span className={s.activeCount}>{sessions.length} active</span>
        )}
        <button
          type="button"
          className={s.closeBtn}
          onClick={toggleCliMonitor}
          aria-label="Close CLI monitor"
        >
          <X size={12} />
        </button>
      </div>

      <div className={s.body}>
        {sessions.length === 0 ? (
          <p className={s.empty}>No active engines</p>
        ) : (
          sessions.map((session) => (
            <SessionRow key={session.tab.id} session={session} />
          ))
        )}
      </div>
    </div>
  )
}
