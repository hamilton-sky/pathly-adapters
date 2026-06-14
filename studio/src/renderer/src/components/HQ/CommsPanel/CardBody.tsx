import React from 'react'
import { Check, History, FileText, Search, Eye } from 'lucide-react'
import type { Message } from '../../CommandCenter/types'
import MarkdownRenderer from '../../../components/shared/MarkdownRenderer/MarkdownRenderer'
import s from './CommsMsgCard.module.css'

export interface CardBodyProps {
  message: Message
  onAnswer?: (messageId: string, optionId: string) => void
  onResolve?: (messageId: string, mode: 'block' | 'note' | 'ignore') => void
}

export function CardBody({ message: m, onAnswer, onResolve }: CardBodyProps) {
  if (m.type === 'artifact') {
    return (
      <>
        <div className={s.art}>
          <span className={s.artIco}><FileText size={15} /></span>
          <span className={s.artName}>{m.artifact}</span>
        </div>
        <div className={s.artExcerpt}><MarkdownRenderer content={m.text} /></div>
        <div className={s.artQ}><Search size={11} />agents can query this by content</div>
      </>
    )
  }

  if (m.type === 'question') {
    return (
      <>
        <MarkdownRenderer content={m.text} className={s.msgText} />
        <div className={s.opts}>
          {(m.options || []).map((o) => (
            <button
              key={o.id}
              type="button"
              className={`${s.opt}${m.answer === o.id ? ` ${s.chosen}` : ''}`}
              onClick={() => onAnswer?.(m.id, o.id)}
            >
              <span className={s.ring} />
              <span>{o.label}</span>
              {o.desc && <span className={s.odesc}>{o.desc}</span>}
            </button>
          ))}
        </div>
        <div className={s.qFoot}>
          {m.status === 'answered'
            ? (
              <span className={`${s.qStatus} ${s.answered}`}>
                <Check size={11} />answered · injected at next /next_action
              </span>
            )
            : (
              <span className={`${s.qStatus} ${s.pending}`}>
                <span className={s.qSpin} />awaiting answer · non-blocking
              </span>
            )}
        </div>
      </>
    )
  }

  if (m.type === 'warning' || m.type === 'escalation') {
    return (
      <>
        <MarkdownRenderer content={m.text} className={s.msgText} />
        {m.status === 'resolved'
          ? (
            <div className={s.msgResolved}>
              <Check size={11} />{m.resolution || 'resolved'}
            </div>
          )
          : (
            <div className={s.msgActs}>
              <button type="button" className={`${s.msgAct} ${s.danger}`} onClick={() => onResolve?.(m.id, 'block')}>
                <History size={12} />Block stage
              </button>
              <button type="button" className={`${s.msgAct} ${s.go}`} onClick={() => onResolve?.(m.id, 'note')}>
                <Check size={12} />Note as future work
              </button>
              <button type="button" className={s.msgAct} onClick={() => onResolve?.(m.id, 'ignore')}>
                <Eye size={12} />Ignore
              </button>
            </div>
          )}
      </>
    )
  }

  return <MarkdownRenderer content={m.text} className={s.msgText} />
}
