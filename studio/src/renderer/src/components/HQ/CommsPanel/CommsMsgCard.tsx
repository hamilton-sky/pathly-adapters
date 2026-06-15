import React, { useState } from 'react'
import { Check, Trash2 } from 'lucide-react'
import type { Message } from '../../CommandCenter/types'
import { AGENTS } from '../../CommandCenter/constants'
import { Avatar } from './Avatar'
import { MessageTypeBadge } from './MessageTypeBadge'
import { CardBody } from './CardBody'
import { SupersedeMenu } from './SupersedeMenu/SupersedeMenu'
import { ConfirmModal } from '../../shared/ConfirmModal/ConfirmModal'
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
  const canDelete = !!onDelete   // every message can be removed from the board
  const [confirming, setConfirming] = useState(false)
  return (
    <div
      className={`${s.msg}${flash ? ` ${s.flash}` : ''}`}
      data-msg={m.id}
      {...(m.supersededBy ? { 'data-superseded': '' } : {})}
    >
      <div className={s.msgCard} data-type={m.type}>
        <div className={s.cardHead}>
          <Avatar from={m.from} />
          <span className={s.msgAuthor}>{agent.label}</span>
          <MessageTypeBadge type={m.type} />
          {m.ack && (
            <span className={s.msgAck}>
              <Check size={11} />acknowledged
            </span>
          )}
          <span className={s.cardActions}>
            {onSupersede && !m.supersededBy && (
              <SupersedeMenu
                message={m}
                candidates={siblings ?? []}
                onSupersede={onSupersede}
              />
            )}
            {canDelete && (
              <button
                type="button"
                className={s.msgDel}
                title="Remove from board"
                aria-label="Delete message"
                onClick={() => setConfirming(true)}
              >
                <Trash2 size={12} />
              </button>
            )}
          </span>
        </div>
        <CardBody message={m} onAnswer={onAnswer} onResolve={onResolve} />
        <div className={s.cardFoot}>
          {m.stage && (
            <span className={s.msgStage} data-stage={m.stage}>{m.stage}</span>
          )}
          <span className={s.msgTime}>{m.time} ago</span>
        </div>
        {confirming && (
          <ConfirmModal
            title="Delete this message?"
            message="It will be removed from the board and its memory."
            onCancel={() => setConfirming(false)}
            onConfirm={() => { setConfirming(false); onDelete?.(m.id) }}
          />
        )}
      </div>
    </div>
  )
}
