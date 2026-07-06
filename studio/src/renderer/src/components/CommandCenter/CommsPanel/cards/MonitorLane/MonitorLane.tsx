import { useState } from 'react'
import { Activity, ChevronRight } from 'lucide-react'
import type { Message } from '../../../types'
import { PhaseRow } from '../PhaseRow/PhaseRow'
import s from './MonitorLane.module.css'

export interface MonitorLaneProps {
  messages: Message[]
}

// Collapsible "Monitor" lane — FSM phase boundaries (`phase`) plus supervisor/system
// lifecycle status (`Started:/Done:`, goal-run started/finished). This is execution-trace
// noise pulled OUT of the message thread so the board reads as the semantic story
// (decisions, artifacts, discoveries, warnings). Collapsed by default; expand to debug.
export function MonitorLane({ messages }: MonitorLaneProps): JSX.Element {
  const [open, setOpen] = useState(false)

  // Newest event drives the collapsed one-line summary (ts is ISO, so lexical max works).
  const latest = messages.reduce<Message | null>(
    (acc, m) => (!acc || (m.ts ?? '') >= (acc.ts ?? '') ? m : acc),
    null,
  )
  const count = messages.length

  return (
    <div className={s.lane}>
      <button
        type="button"
        className={s.head}
        onClick={() => setOpen((v) => !v)}
        {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
        aria-label={open ? 'Collapse monitor' : 'Expand monitor'}
      >
        <Activity size={12} className={s.icon} />
        <span className={s.title}>Monitor</span>
        <span className={s.count}>{count} event{count !== 1 ? 's' : ''}</span>
        {latest && (
          <span className={s.last}>· {latest.text} · {latest.time} ago</span>
        )}
        <ChevronRight size={13} className={`${s.chev}${open ? ` ${s.chevOpen}` : ''}`} />
      </button>
      {open && (
        <div className={s.body}>
          {messages.map((m) => (
            <PhaseRow key={m.id} message={m} />
          ))}
        </div>
      )}
    </div>
  )
}
