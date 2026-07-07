import { Timestamp } from '../../../../Timestamp/Timestamp'
import { MessageTypeBadge } from '../../MessageTypeBadge/MessageTypeBadge'
import { agentMeta } from '../../../constants'
import { HoverCard } from '../HoverCard/HoverCard'
import { TileDeleteButton } from '../TileDeleteButton/TileDeleteButton'
import { absoluteTime, firstLine } from '../format'
import type { Message } from '../../../types'
import hc from '../HoverCard/HoverCard.module.css'
import s from './MessageTile.module.css'

interface Props {
  message: Message
  onOpen: (message: Message) => void
  onDelete?: (message: Message) => void
}

// Message sticker — a badge note. Type carried by the reused MessageTypeBadge;
// warning / escalation get a full tint (data-type). Click → MessageDetailModal.
export function MessageTile({ message: m, onOpen, onDelete }: Props): JSX.Element {
  const title = firstLine(m.text)
  const author = agentMeta(m.from).label
  const full = absoluteTime(m.ts)

  return (
    <HoverCard
      card={
        <>
          <div className={hc.pvHead}>
            <MessageTypeBadge type={m.type} />
            <span className={hc.pvTime}>{author}</span>
          </div>
          <div className={hc.pvTitle}>{title}</div>
          <div className={hc.pvMeta}>{full}</div>
        </>
      }
    >
      <div
        role="button"
        tabIndex={0}
        className={s.tile}
        data-type={m.type}
        onClick={() => onOpen(m)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onOpen(m)
          }
        }}
      >
        <div className={s.top}>
          <MessageTypeBadge type={m.type} />
          <span className={s.time} title={full}>
            <Timestamp value={m.ts} />
          </span>
        </div>
        <div className={s.text}>{title}</div>
        <div className={s.author}>{author}</div>
        {onDelete && <TileDeleteButton onDelete={() => onDelete(m)} />}
      </div>
    </HoverCard>
  )
}
