import React from 'react'
import { Check } from 'lucide-react'
import type { Message } from '../CommandCenter/types'
import { AGENTS } from '../CommandCenter/constants'
import { Avatar } from './Avatar'
import { MessageTypeBadge } from './MessageTypeBadge'
import { CardBody } from './CardBody'
import s from './CommsMsgCard.module.css'

export interface CommsMsgCardProps {
  message: Message
  flash?: boolean
  onAnswer?: (messageId: string, optionId: string) => void
  onResolve?: (messageId: string, mode: 'block' | 'note' | 'ignore') => void
}

export function CommsMsgCard({ message: m, flash, onAnswer, onResolve }: CommsMsgCardProps) {
  const agent = AGENTS[m.from]
  return (
    <div className={`${s.msg}${flash ? ` ${s.flash}` : ''}`} data-msg={m.id}>
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
      </div>

      <div className={s.msgCard} data-type={m.type}>
        <MessageTypeBadge type={m.type} />
        <CardBody message={m} onAnswer={onAnswer} onResolve={onResolve} />
      </div>
    </div>
  )
}
