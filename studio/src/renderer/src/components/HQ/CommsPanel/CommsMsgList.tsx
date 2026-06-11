import React from 'react'
import { Star, MessageSquare, Trash2 } from 'lucide-react'
import type { BoardScope, Message } from '../CommandCenter/types'
import { AGENTS } from '../CommandCenter/constants'
import { CommsMsgCard } from './CommsMsgCard'
import MarkdownRenderer from '../../../components/shared/MarkdownRenderer/MarkdownRenderer'
import s from './CommsMsgList.module.css'

export interface CommsMsgListProps {
  scope: BoardScope
  messages: Message[]
  flashId?: string | null
  onAnswer?: (messageId: string, optionId: string) => void
  onResolve?: (messageId: string, mode: 'block' | 'note' | 'ignore') => void
  onDelete?: (messageId: string) => void
}

// Pinned decisions tray + the message thread.
export function CommsMsgList({ scope, messages, flashId, onAnswer, onResolve, onDelete }: CommsMsgListProps) {
  const pins = messages.filter((m) => m.pinned)
  const thread = messages.filter((m) => !m.pinned)

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
                  {AGENTS[m.from].label}{m.stage ? ` · ${m.stage}` : ''} · {m.time} ago ·{' '}
                  <span className={s.pinScope}>{scope} scope</span>
                </div>
              </div>
              {m.from === 'you' && !m.readByAgent && onDelete && (
                <button
                  type="button"
                  className={s.pinDel}
                  title="Delete — not yet read by any agent"
                  aria-label="Delete message"
                  onClick={() => onDelete(m.id)}
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
          <CommsMsgCard
            key={m.id}
            message={m}
            flash={flashId === m.id}
            onAnswer={onAnswer}
            onResolve={onResolve}
            onDelete={onDelete}
          />
        ))
        : (
          <div className={s.empty}>
            <MessageSquare size={22} />
            <p>No messages on this board yet.</p>
          </div>
        )}
    </div>
  )
}
