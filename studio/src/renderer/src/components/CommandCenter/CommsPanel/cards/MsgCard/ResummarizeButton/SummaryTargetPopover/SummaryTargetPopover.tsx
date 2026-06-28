import { useEffect, useRef, useState, useLayoutEffect } from 'react'
import { createPortal } from 'react-dom'
import { AiTargetSelector } from '../../../../../../shared/AiTargetSelector/AiTargetSelector'
import type { AiSelection } from '../../../../../../../services/aiRouter'
import type { SummaryStyle } from '../../../../../../../store/commsApi'
import { fetchSummaryFormat } from '../../../../../../../services/summaryFormat'
import MarkdownRenderer from '../../../../../../shared/MarkdownRenderer/MarkdownRenderer'
import s from './SummaryTargetPopover.module.css'

interface Props {
  anchorEl: HTMLButtonElement | null
  value: AiSelection
  onChange: (sel: AiSelection) => void
  style: SummaryStyle
  onStyleChange: (style: SummaryStyle) => void
  note: string
  onNoteChange: (note: string) => void
  onClose: () => void
}

const POPOVER_WIDTH = 220

// Summary DEPTH options — gist (precision) → topic-map (balanced) → detailed (recall).
// The output-shape PREVIEW is not hardcoded here — it is fetched from the depth's template
// file (the same one compose injects into the prompt), see formatPreview below.
const STYLE_OPTIONS: { value: SummaryStyle; label: string; hint: string }[] = [
  { value: 'gist', label: 'Gist', hint: 'One sentence — the core point (precision)' },
  { value: 'topic-map', label: 'Topic map', hint: 'One line per section (balanced)' },
  { value: 'detailed', label: 'Detailed', hint: 'Section + key points (recall)' },
]

// Gear-anchored popover for the per-artifact AI target selector. Portals to body,
// positioned relative to the gear button (above or below depending on viewport space).
// Outside-click + Escape to close, matching DecomposeConfigPopover's idiom.
export function SummaryTargetPopover({ anchorEl, value, onChange, style, onStyleChange, note, onNoteChange, onClose }: Props): JSX.Element | null {
  const ref = useRef<HTMLDivElement>(null)
  // Local draft — persist on blur (one POST per edit, not per keystroke).
  const [noteDraft, setNoteDraft] = useState(note)
  const activeStyle = STYLE_OPTIONS.find((o) => o.value === style) ?? STYLE_OPTIONS[1]
  // The output-format preview is the SAME contract the agent receives — fetched from the depth's
  // template file (core/templates/summary/<style>.md), never hardcoded, so they can't drift.
  const [formatPreview, setFormatPreview] = useState('')
  useEffect(() => {
    let alive = true
    void fetchSummaryFormat(style).then((f) => { if (alive) setFormatPreview(f) })
    return () => { alive = false }
  }, [style])

  useLayoutEffect(() => {
    if (!anchorEl || !ref.current) return
    const r = anchorEl.getBoundingClientRect()
    const popH = ref.current.offsetHeight || 100
    let l = r.right - POPOVER_WIDTH
    if (l < 8) l = 8
    if (l + POPOVER_WIDTH > window.innerWidth - 8) l = window.innerWidth - 8 - POPOVER_WIDTH
    // Prefer above the anchor (card footers may be near the bottom), fall back below.
    const topAbove = r.top - popH - 6
    const top = topAbove >= 8 ? topAbove : r.bottom + 6
    ref.current.style.setProperty('--pop-top', `${top}px`)
    ref.current.style.setProperty('--pop-left', `${l}px`)
  }, [anchorEl])

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node
      if (ref.current && !ref.current.contains(t) && anchorEl && !anchorEl.contains(t)) onClose()
    }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [anchorEl, onClose])

  return createPortal(
    <div ref={ref} className={s.popover} role="dialog" aria-label="Choose AI target and summary depth">
      <div className={s.heading}>Summary depth</div>
      <div className={s.styleRow}>
        {STYLE_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            className={s.styleBtn}
            {...(style === opt.value ? { 'data-active': '' } : {})}
            onClick={() => onStyleChange(opt.value)}
            title={opt.hint}
          >
            {opt.label}
          </button>
        ))}
      </div>
      {formatPreview && (
        <div className={s.formatBox} aria-label={`${activeStyle.label} output format`}>
          <div className={s.formatTitle}>{activeStyle.label}</div>
          <MarkdownRenderer content={formatPreview} className={s.formatMd} />
        </div>
      )}
      <div className={s.heading}>AI target for this artifact</div>
      <div className={s.body}>
        <AiTargetSelector value={value} onChange={(sel) => { onChange(sel) }} allowOff />
      </div>
      <div className={s.heading}>Special request (optional)</div>
      <div className={s.body}>
        <textarea
          className={s.note}
          value={noteDraft}
          rows={3}
          placeholder="e.g. focus on the security parts; write for a non-technical reader"
          onChange={(e) => setNoteDraft(e.target.value)}
          onBlur={() => { if (noteDraft !== note) onNoteChange(noteDraft) }}
        />
      </div>
    </div>,
    document.body,
  )
}
