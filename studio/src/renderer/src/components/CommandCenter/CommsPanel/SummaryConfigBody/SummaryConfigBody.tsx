import { useEffect, useState } from 'react'
import { AiTargetSelector } from '../../../shared/AiTargetSelector/AiTargetSelector'
import { StylePicker, STYLE_OPTIONS } from '../../../shared/StylePicker/StylePicker'
import type { AiSelection } from '../../../../services/aiRouter'
import type { SummaryStyle } from '../../../../store/commsApi'
import { fetchSummaryFormat } from '../../../../services/summaryFormat'
import MarkdownRenderer from '../../../shared/MarkdownRenderer/MarkdownRenderer'
import s from './SummaryConfigBody.module.css'

interface Props {
  style: SummaryStyle
  onStyleChange: (style: SummaryStyle) => void
  selection: AiSelection | null
  onSelectionChange: (sel: AiSelection) => void
  note: string
  onNoteChange: (note: string) => void
  /** Heading for the AI-target section (differs per caller). */
  targetLabel: string
  /** Heading for the free-text instruction section. */
  noteLabel: string
  notePlaceholder: string
}

// Shared sectioned body for BOTH summary popovers — the per-artifact Re-summarize
// gear and the board-level SummaryConfig gear — so the two can't visually drift.
// Layout: Summary depth (+ a live output-format preview pulled from the depth's
// template) → AI target → a free-text instruction. Persistence differs by caller
// (artifact row vs per-board setting) and flows entirely through the on*Change
// callbacks; the note uses a local draft committed on blur.
export function SummaryConfigBody({
  style, onStyleChange, selection, onSelectionChange, note, onNoteChange,
  targetLabel, noteLabel, notePlaceholder,
}: Props): JSX.Element {
  const [noteDraft, setNoteDraft] = useState(note)
  const activeStyle = STYLE_OPTIONS.find((o) => o.value === style) ?? STYLE_OPTIONS[1]
  // The output-format preview is the SAME contract the agent receives — fetched from
  // the depth's template file (core/templates/summary/<style>.md), never hardcoded.
  const [formatPreview, setFormatPreview] = useState('')

  // Resync the draft if the stored note loads/changes underneath us (async seed).
  useEffect(() => { setNoteDraft(note) }, [note])

  useEffect(() => {
    let alive = true
    void fetchSummaryFormat(style).then((f) => { if (alive) setFormatPreview(f) })
    return () => { alive = false }
  }, [style])

  return (
    <>
      <div className={s.heading}>Summary depth</div>
      <div className={s.styleWrap}>
        <StylePicker value={style} onChange={onStyleChange} />
      </div>
      {formatPreview && (
        <div className={s.formatBox} aria-label={`${activeStyle.label} output format`}>
          <div className={s.formatTitle}>{activeStyle.label}</div>
          <MarkdownRenderer
            content={
              `**Description** — a 1–2 sentence “what it is & why it matters” ` +
              `(refreshes the card’s Description).\n\n**Summary**\n${formatPreview}`
            }
            className={s.formatMd}
          />
        </div>
      )}
      <div className={s.heading}>{targetLabel}</div>
      <div className={s.body}>
        <AiTargetSelector value={selection} onChange={onSelectionChange} allowOff />
      </div>
      <div className={s.heading}>{noteLabel}</div>
      <div className={s.body}>
        <textarea
          className={s.note}
          value={noteDraft}
          rows={3}
          placeholder={notePlaceholder}
          onChange={(e) => setNoteDraft(e.target.value)}
          onBlur={() => { if (noteDraft !== note) onNoteChange(noteDraft) }}
        />
      </div>
    </>
  )
}
