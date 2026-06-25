import React, { useState } from 'react'
import { Star, MessageSquare, Trash2 } from 'lucide-react'
import type { BoardScope, Message } from '../../types'
import { agentMeta } from '../../constants'
import { MsgCard } from '../cards/MsgCard/MsgCard'
import { PhaseRow } from '../cards/PhaseRow/PhaseRow'
import { ConfirmModal } from '../../../shared/ConfirmModal/ConfirmModal'
import MarkdownRenderer from '../../../../components/shared/MarkdownRenderer/MarkdownRenderer'
import s from './CommsMsgList.module.css'

export interface CommsMsgListProps {
  scope: BoardScope
  messages: Message[]
  searchResults?: Message[] | null
  searchTerm?: string
  flashId?: string | null
  onAnswer?: (messageId: string, optionId: string) => void
  onResolve?: (messageId: string, mode: 'block' | 'note' | 'ignore') => void
  onDelete?: (messageId: string) => void
  onSupersede?: (oldId: string, newId: string) => void
}

// Pinned decisions tray + the message thread.
export function CommsMsgList({ scope, messages, searchResults, searchTerm, flashId, onAnswer, onResolve, onDelete, onSupersede }: CommsMsgListProps) {
  // Pinned-message delete confirmation (cards manage their own confirm state).
  const [confirmPinId, setConfirmPinId] = useState<string | null>(null)

  // Search overlay — replaces the normal thread when active.
  if (searchResults) {
    return (
      <div className={s.thread}>
        <div className={s.searchHead}>
          {searchResults.length} result{searchResults.length !== 1 ? 's' : ''} for &ldquo;{searchTerm}&rdquo;
        </div>
        {searchResults.map((m) => (
          <MsgCard
            key={m.id}
            message={m}
            flash={false}
            onAnswer={onAnswer}
            onResolve={onResolve}
            onDelete={onDelete}
            onSupersede={onSupersede}
            siblings={messages}
          />
        ))}
      </div>
    )
  }

  const pins = messages.filter((m) => m.pinned)
  // Goals and tasks live in the dedicated "Goals & Tasks" board view, not the
  // message thread — filter them out here so the Messages view stays a clean log.
  const thread = messages.filter(
    (m) => !m.pinned && m.type !== 'goal' && m.type !== 'task',
  )

  return (
    <div className={s.thread}>
      {pins.length > 0 && (
        <div className={s.pins}>
          {pins.map((m) => (
            <div key={m.id} className={`${s.pin}${flashId === m.id ? ` ${s.flash}` : ''}`}>
              <Star size={14} className={s.pinIcon} />
              <div className={s.pinBody}>
                <MarkdownRenderer content={m.text} className={s.pinTxt} />
                <div className={s.pinMeta}>
                  {agentMeta(m.from).label}{m.stage ? ` · ${m.stage}` : ''} · {m.time} ago ·{' '}
                  <span className={s.pinScope}>{scope} scope</span>
                </div>
              </div>
              {onDelete && (
                <button
                  type="button"
                  className={s.pinDel}
                  title="Remove from board"
                  aria-label="Delete message"
                  onClick={() => setConfirmPinId(m.id)}
                >
                  <Trash2 size={12} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {thread.length > 0
        ? thread.map((m) => (
          m.type === 'phase' ? (
            <PhaseRow key={m.id} message={m} />
          ) : (
            <MsgCard
              key={m.id}
              message={m}
              flash={flashId === m.id}
              onAnswer={onAnswer}
              onResolve={onResolve}
              onDelete={onDelete}
              onSupersede={onSupersede}
              siblings={messages}
            />
          )
        ))
        : (
          <div className={s.empty}>
            <MessageSquare size={22} />
            <p>No messages on this board yet.</p>
          </div>
        )}

      {confirmPinId && (
        <ConfirmModal
          title="Remove this pinned message?"
          message="It will be removed from the board and its memory."
          onCancel={() => setConfirmPinId(null)}
          onConfirm={() => { const id = confirmPinId; setConfirmPinId(null); onDelete?.(id) }}
        />
      )}
    </div>
  )
}
