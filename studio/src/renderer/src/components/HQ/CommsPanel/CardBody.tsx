import React from 'react'
import { Check, History, FileText, Search, Eye, SquarePen } from 'lucide-react'
import type { Message } from '../../CommandCenter/types'
import MarkdownRenderer from '../../../components/shared/MarkdownRenderer/MarkdownRenderer'
import { useUiStore } from '../../../store/uiStore'
import { useProjectStore } from '../../../store/projectStore'
import s from './CommsMsgCard.module.css'

// Open an artifact file in the markdown editor panel.
function openArtifactInEditor(path: string): void {
  const name = path.split(/[/\\]/).pop() ?? path
  useProjectStore.getState().setSelectedItem({ name, path, type: 'plan' })
  useUiStore.getState().setActivePanel('editor')
}

export interface CardBodyProps {
  message: Message
  onAnswer?: (messageId: string, optionId: string) => void
  onResolve?: (messageId: string, mode: 'block' | 'note' | 'ignore') => void
}

export function CardBody({ message: m, onAnswer, onResolve }: CardBodyProps) {
  const supersededBanner = m.supersededBy
    ? <div className={s.supersededNote}>superseded — see newer message</div>
    : null

  if (m.type === 'artifact') {
    return (
      <>
        {supersededBanner}
        <div className={s.art}>
          <span className={s.artIco}><FileText size={15} /></span>
          <span className={s.artName}>{m.artifact}</span>
          {m.artifactPath && (
            <button
              type="button"
              className={s.artOpen}
              title="Open this artifact in the editor"
              onClick={() => openArtifactInEditor(m.artifactPath as string)}
            >
              <SquarePen size={11} /> Open in editor
            </button>
          )}
        </div>
        <div className={s.artExcerpt}><MarkdownRenderer content={m.text} /></div>
        <div className={s.artQ}><Search size={11} />agents can query this by content</div>
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

  return (
    <>
      {supersededBanner}
      <MarkdownRenderer content={m.text} className={s.msgText} />
    </>
  )
}
