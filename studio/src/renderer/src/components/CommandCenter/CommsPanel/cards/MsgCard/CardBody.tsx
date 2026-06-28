import React, { useState, useEffect } from 'react'
import { Check, History, FileText, Search, Eye, ChevronRight } from 'lucide-react'
import type { Message } from '../../../types'
import MarkdownRenderer from '../../../../shared/MarkdownRenderer/MarkdownRenderer'
import { fetchArtifacts } from '../../../../../store/commsApi'
import s from './MsgCard.module.css'

export interface CardBodyProps {
  message: Message
  onAnswer?: (messageId: string, optionId: string) => void
  onResolve?: (messageId: string, mode: 'block' | 'note' | 'ignore') => void
}

export function CardBody({ message: m, onAnswer, onResolve }: CardBodyProps) {
  const [expanded, setExpanded] = useState(false)
  // The AI summary lives on the comms_artifacts row (not the message) — fetch it lazily
  // when an artifact card is expanded so it shows inline, not only in the Details modal.
  const [summary, setSummary] = useState<string | null>(null)
  useEffect(() => {
    if (m.type !== 'artifact' || !expanded) return
    let alive = true
    void fetchArtifacts(m.id).then((rows) => { if (alive) setSummary(rows[0]?.summary ?? null) })
    return () => { alive = false }
  }, [m.type, m.id, expanded])
  const supersededBanner = m.supersededBy
    ? <div className={s.supersededNote}>superseded — see newer message</div>
    : null

  if (m.type === 'artifact') {
    return (
      <>
        {supersededBanner}
        <button
          type="button"
          className={s.artHead}
          onClick={() => setExpanded((e) => !e)}
          {...(expanded ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
          aria-label={expanded ? 'Hide artifact summary' : 'Show artifact summary'}
        >
          <span className={s.artIco}><FileText size={15} /></span>
          <span className={s.artName}>{m.artifact}</span>
          <span className={s.artChevron} {...(expanded ? { 'data-open': '' } : {})}>
            <ChevronRight size={14} />
          </span>
        </button>
        {expanded && (
          <>
            {summary && (
              <>
                <div className={s.artSummaryLabel}>AI Summary</div>
                <div className={s.artExcerpt}><MarkdownRenderer content={summary} /></div>
                <div className={s.artSummaryLabel}>Description</div>
              </>
            )}
            <div className={s.artExcerpt}><MarkdownRenderer content={m.text} /></div>
            <div className={s.artQ}><Search size={11} />agents can query this by content</div>
          </>
        )}
      </>
    )
  }

  if (m.type === 'question') {
    return (
      <>
        {supersededBanner}
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
        {supersededBanner}
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

  // Goals and tasks no longer render in the message thread — they live in the
  // dedicated "Goals & Tasks" board view (GoalsView). The Messages view filters
  // them out, so CardBody never receives them here.

  return (
    <>
      {supersededBanner}
      <MarkdownRenderer content={m.text} className={s.msgText} />
    </>
  )
}
