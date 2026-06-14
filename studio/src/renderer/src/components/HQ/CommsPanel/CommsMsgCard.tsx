import React from 'react'
import { Check, Trash2 } from 'lucide-react'
import type { Message } from '../../CommandCenter/types'
import { AGENTS } from '../../CommandCenter/constants'
import { Avatar } from './Avatar'
import { MessageTypeBadge } from './MessageTypeBadge'
import { CardBody } from './CardBody'
import { SupersedeMenu } from './SupersedeMenu/SupersedeMenu'
import s from './CommsMsgCard.module.css'

export interface CommsMsgCardProps {
  message: Message
  flash?: boolean
  onAnswer?: (messageId: string, optionId: string) => void
  onResolve?: (messageId: string, mode: 'block' | 'note' | 'ignore') => void
  onDelete?: (messageId: string) => void
  onSupersede?: (oldId: string, newId: string) => void
  siblings?: Message[]
}

export function CommsMsgCard({ message: m, flash, onAnswer, onResolve, onDelete, onSupersede, siblings }: CommsMsgCardProps) {
  const agent = AGENTS[m.from]
  const canDelete = m.from === 'you' && !m.readByAgent && !!onDelete
  return (
    <div
      className={`${s.msg}${flash ? ` ${s.flash}` : ''}`}
      data-msg={m.id}
      {...(m.supersededBy ? { 'data-superseded': '' } : {})}
    >
      <div className={s.msgMeta}>
        <Avatar from={m.from} />
        <span className={s.msgAuthor}>{agent.label}</span>
        {m.stage && (
          <span className={s.msgStage} data-stage={m.stage}>{m.stage}</span>
        )}
        {m.ack && (
          <span className={s.msgAck}>
            <Check size={11} />acknowledged
          </span>
        )}
        <span className={s.msgTime}>{m.time} ago</span>
        {canDelete && (
          <button
            type="button"
            className={s.msgDel}
            title="Delete — not yet read by any agent"
            aria-label="Delete message"
            onClick={() => onDelete?.(m.id)}
          >
            <Trash2 size={12} />
          </button>
        )}
        {onSupersede && !m.supersededBy && (
          <SupersedeMenu
            message={m}
            candidates={siblings ?? []}
            onSupersede={onSupersede}
          />
        )}
      </div>

      <div className={s.msgCard} data-type={m.type}>
        <MessageTypeBadge type={m.type} />
        <CardBody message={m} onAnswer={onAnswer} onResolve={onResolve} />
      </div>
    </div>
  )
}
