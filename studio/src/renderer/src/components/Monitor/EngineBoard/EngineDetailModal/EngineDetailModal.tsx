import React, { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import type { MonitorEngine } from '../types'
import { statusColor, statusLabel, adapterCommand } from '../constants'
import { CategoryBadge } from '../CategoryBadge/CategoryBadge'
import { AdapterBadge } from '../AdapterBadge/AdapterBadge'
import { StagePill } from '../StagePill/StagePill'
import { StatusDot } from '../StatusDot/StatusDot'
import { EngineControls } from '../EngineControls/EngineControls'
import s from './EngineDetailModal.module.css'

interface Props {
  engine: MonitorEngine
  onClose: () => void
  onAction?: (engineId: string, actionId: string) => void
  /** Open the full RunDetailPage for this run (entrance #1). Absent → the button is hidden. */
  onOpenRun?: (runId: string) => void
}

interface LogLine { text: string; tone: 'muted' | 'secondary' | 'accent' | 'green' }

function buildLog(e: MonitorEngine): LogLine[] {
  const lines: LogLine[] = [
    { text: `$ ${adapterCommand(e.adapter)} -p  # ${e.role} · ${e.feature}`, tone: 'muted' },
    { text: e.snippet, tone: 'secondary' },
  ]
  if (e.status === 'queued') lines.push({ text: 'awaiting spawn slot…', tone: 'muted' })
  else if (e.status === 'done') lines.push({ text: `runner: finished · ${e.tokens} · ${e.cost}`, tone: 'green' })
  else lines.push({ text: `runner: ${String(e.stage).toLowerCase()} · streaming events`, tone: 'accent' })
  return lines
}

// Full detail view for one engine. Header (category / adapter / role / status) →
// feature + stage → metric tiles → live output → contextual controls. The controls
// live *here* rather than on every card, keeping the board scannable.
export function EngineDetailModal({ engine: e, onClose, onAction, onOpenRun }: Props): JSX.Element {
  const boxRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onKey(ev: KeyboardEvent): void {
      if (ev.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const metrics = [
    { label: 'Tokens',  value: e.tokens.replace(' tok', ''), tone: '' },
    { label: 'Cost',    value: e.cost,    tone: e.cost === '-' ? 'muted' : 'green' },
    { label: 'Elapsed', value: e.elapsed, tone: '' },
    { label: 'Started', value: e.started, tone: 'secondary' },
  ]

  return createPortal(
    <div className={s.backdrop} onClick={(ev) => { if (ev.target === ev.currentTarget) onClose() }}>
      <div ref={boxRef} role="dialog" aria-modal="true" aria-label={`${e.feature} engine detail`} className={s.box}>
        <button type="button" className={s.close} onClick={onClose} aria-label="Close">
          <X size={15} />
        </button>

        <div className={s.header}>
          <div className={s.badges}>
            <CategoryBadge category={e.category} />
            <AdapterBadge adapter={e.adapter} />
            <span className={s.role}>{e.role}</span>
            <span className={s.statusWrap}>
              <StatusDot status={e.status} />
              <span className={s.statusText} style={{ '--status-color': statusColor(e.status) } as React.CSSProperties}>
                {statusLabel(e.status)}
              </span>
            </span>
          </div>
          <div className={s.titleRow}>
            <span className={s.feature}>{e.feature}</span>
            <StagePill stage={e.stage} />
          </div>
          <div className={s.model}>{e.model ? e.model : '—'}</div>
        </div>

        <div className={s.metrics}>
          {metrics.map((m) => (
            <div key={m.label} className={s.metric}>
              <span className={s.metricValue} data-tone={m.tone}>{m.value}</span>
              <span className={s.metricLabel}>{m.label}</span>
            </div>
          ))}
        </div>

        <div className={s.logSection}>
          <div className={s.logLabel}>Live output</div>
          <div className={s.log}>
            {buildLog(e).map((l, i) => (
              <div key={i} className={s.logLine} data-tone={l.tone}>{l.text}</div>
            ))}
          </div>
        </div>

        <div className={s.footer}>
          <EngineControls
            status={e.status}
            category={e.category}
            onAction={(actionId) => onAction?.(e.id, actionId)}
          />
          {onOpenRun && e.status !== 'queued' && (
            <>
              <span className={s.footSpacer} />
              <button type="button" className={s.openRun} onClick={() => onOpenRun(e.id)}>
                Open run →
              </button>
            </>
          )}
        </div>
      </div>
    </div>,
    document.body,
  )
}
