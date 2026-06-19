import { useState } from 'react'
import { ChevronUp, ChevronDown, X, Pause, Play, SlidersHorizontal } from 'lucide-react'
import { useTerminalStore } from '../../store/terminalStore'
import s from './SpawnQueuePanel.module.css'

const CAPS_KEY = 'pathly:spawnCaps'

function qc(action: QueueAction): void {
  void window.pathly?.terminal?.queueControl?.(action)
}

export function persistCaps(caps: SpawnCaps): void {
  try { localStorage.setItem(CAPS_KEY, JSON.stringify(caps)) } catch { /* ignore */ }
}

export function loadCaps(): SpawnCaps | null {
  try {
    const v = localStorage.getItem(CAPS_KEY)
    return v ? (JSON.parse(v) as SpawnCaps) : null
  } catch { return null }
}

function CapInput({ label, value, onCommit }: { label: string; value: number; onCommit: (n: number) => void }): JSX.Element {
  return (
    <label className={s.capField}>
      <span>{label}</span>
      <input
        type="number"
        min={0}
        max={32}
        defaultValue={value}
        key={value}
        className={s.capInput}
        onBlur={(e) => onCommit(Number(e.currentTarget.value))}
        onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur() }}
      />
    </label>
  )
}

/** Queue management for headless CLI runs: reorder, cancel, pause/resume, and edit the caps. */
export function SpawnQueuePanel({ spawnQueue }: { spawnQueue: SpawnState }): JSX.Element | null {
  const tabs = useTerminalStore((st) => st.tabs)
  const [showCaps, setShowCaps] = useState(false)
  const queue = spawnQueue.queued
  const labelFor = (id: string): string => tabs.find((t) => t.id === id)?.label ?? id

  // Only render when there's something to manage or the user is inspecting limits.
  if (queue.length === 0 && !spawnQueue.paused && !showCaps) {
    return (
      <button type="button" className={s.limitsLink} onClick={() => setShowCaps(true)}>
        <SlidersHorizontal size={10} /> limits
      </button>
    )
  }

  const setCap = (patch: Partial<SpawnCaps>): void => {
    const next = { ...spawnQueue.caps, ...patch }
    persistCaps(next)
    qc({ type: 'set-caps', caps: patch })
  }

  return (
    <div className={s.panel}>
      <div className={s.head}>
        <span className={s.headLabel}>QUEUE ({queue.length})</span>
        {spawnQueue.paused ? (
          <button type="button" className={s.ctlBtn} data-active="true" onClick={() => qc({ type: 'resume' })}>
            <Play size={11} /> resume
          </button>
        ) : (
          <button type="button" className={s.ctlBtn} onClick={() => qc({ type: 'pause' })} disabled={queue.length === 0}>
            <Pause size={11} /> pause
          </button>
        )}
        <button type="button" className={s.ctlBtn} data-active={showCaps ? 'true' : undefined} onClick={() => setShowCaps((v) => !v)} aria-label="Edit limits">
          <SlidersHorizontal size={11} />
        </button>
      </div>

      {showCaps && (
        <div className={s.caps}>
          <CapInput label="total" value={spawnQueue.caps.global} onCommit={(n) => setCap({ global: n })} />
          <CapInput label="headless" value={spawnQueue.caps.headless} onCommit={(n) => setCap({ headless: n })} />
          <CapInput label="chat" value={spawnQueue.caps.interactive} onCommit={(n) => setCap({ interactive: n })} />
        </div>
      )}

      {queue.map((id, i) => (
        <div key={id} className={s.row}>
          <span className={s.pos}>{i + 1}</span>
          <span className={s.rowLabel}>{labelFor(id)}</span>
          <button type="button" className={s.iconBtn} disabled={i === 0} onClick={() => qc({ type: 'reorder', tabId: id, dir: 'up' })} aria-label="Move up"><ChevronUp size={12} /></button>
          <button type="button" className={s.iconBtn} disabled={i === queue.length - 1} onClick={() => qc({ type: 'reorder', tabId: id, dir: 'down' })} aria-label="Move down"><ChevronDown size={12} /></button>
          <button type="button" className={s.iconBtn} data-danger onClick={() => { qc({ type: 'cancel', tabId: id }); useTerminalStore.getState().closeTab(id) }} aria-label="Remove from queue"><X size={12} /></button>
        </div>
      ))}
    </div>
  )
}
