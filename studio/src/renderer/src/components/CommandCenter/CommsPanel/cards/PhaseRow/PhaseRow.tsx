import { Activity } from 'lucide-react'
import type { Message } from '../../../types'
import { agentMeta } from '../../../constants'
import s from './PhaseRow.module.css'

export interface PhaseRowProps {
  message: Message
}

// Compact, muted timeline row for `phase` board messages (FSM phase boundaries,
// unified-ai-routing Conv 6). Deliberately distinct from decision/artifact cards:
// observability only — no avatar, badge, or actions — so the phase stream reads as
// a lightweight progress log instead of cluttering the thread with full cards.
export function PhaseRow({ message: m }: PhaseRowProps): JSX.Element {
  const author = m.from && m.from !== 'you' ? agentMeta(m.from).label : ''
  return (
    <div className={s.row} data-msg={m.id}>
      <Activity size={11} className={s.icon} />
      <span className={s.label}>{m.text}</span>
      {author && <span className={s.author}>{author}</span>}
      <span className={s.time}>{m.time} ago</span>
    </div>
  )
}
