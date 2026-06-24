import React, { useState } from 'react'
import { Check, Trash2, Info } from 'lucide-react'
import type { Message } from '../../../types'
import { agentMeta } from '../../../constants'
import { Avatar } from '../../Avatar'
import { MessageTypeBadge } from '../../MessageTypeBadge'
import { CardBody } from './CardBody'
import { SupersedeMenu } from '../../SupersedeMenu/SupersedeMenu'
import { ConfirmModal } from '../../../../shared/ConfirmModal/ConfirmModal'
import { ArtifactModal } from '../../ArtifactModal/ArtifactModal'
import { Tooltip } from '../../../../ui'
import { useCommsStore } from '../../../../../store/commsStore'
import s from './MsgCard.module.css'

const SUMMARY_LABEL = {
  summarizing: 'summarizing…',
  ready: '📝 summary',
  failed: '⚠ summary failed',
} as const

export interface MsgCardProps {
  message: Message
  flash?: boolean
  onAnswer?: (messageId: string, optionId: string) => void
  onResolve?: (messageId: string, mode: 'block' | 'note' | 'ignore') => void
  onDelete?: (messageId: string) => void
  onSupersede?: (oldId: string, newId: string) => void
  siblings?: Message[]
}

export function MsgCard({ message: m, flash, onAnswer, onResolve, onDelete, onSupersede, siblings }: MsgCardProps) {
  const agent = agentMeta(m.from)
  const canDelete = !!onDelete
  const [confirming, setConfirming] = useState(false)
  const [showDetails, setShowDetails] = useState(false)
  const summaryState = useCommsStore((st) => st.summaryStatus[m.id])
  return (
    <div
      className={`${s.msg}${flash ? ` ${s.flash}` : ''}`}
      data-msg={m.id}
      {...(m.supersededBy ? { 'data-superseded': '' } : {})}
    >
      <div className={s.msgCard} data-type={m.type}>
        <div className={s.cardHead}>
          <Avatar from={m.from} />
          {/* 'you' is already shown by the avatar chip — don't repeat the label. */}
          {m.from !== 'you' && <span className={s.msgAuthor}>{agent.label}</span>}
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
          {m.type === 'artifact' && (
            <Tooltip label="Artifact details — metadata, preview, open in editor" placement="top">
              <button
                type="button"
                className={s.artOpen}
                aria-label="Show artifact details"
                onClick={() => setShowDetails(true)}
              >
                <Info size={11} /> Details
              </button>
            </Tooltip>
          )}
          {m.type === 'artifact' && summaryState && (
            <span className={s.summaryBadge} data-summary={summaryState}>
              {SUMMARY_LABEL[summaryState]}
            </span>
          )}
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
        {showDetails && (
          <ArtifactModal message={m} onClose={() => setShowDetails(false)} />
        )}
      </div>
    </div>
  )
}
