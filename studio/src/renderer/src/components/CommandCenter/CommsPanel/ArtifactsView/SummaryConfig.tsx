import { useRef, useState } from 'react'
import { SlidersHorizontal } from 'lucide-react'
import { Tooltip } from '../../../ui'
import { isOff, type AiSelection } from '../../../../services/aiRouter'
import type { SummaryStyle } from '../../../../store/commsApi'
import { SummaryConfigPopover } from './SummaryConfigPopover'
import s from './SummaryConfig.module.css'

interface Props {
  selection: AiSelection | null
  onSelectionChange: (sel: AiSelection) => void
  style: SummaryStyle
  onStyleChange: (style: SummaryStyle) => void
  /** Per-board default instruction, applied to every artifact dropped on this board. */
  note: string
  onNoteChange: (note: string) => void
}

// Icon trigger for the artifact-summary settings (which AI target + what depth
// summarizes dropped artifacts). Replaces the old always-on two-row toolbar inside
// ArtifactsView, collapsing that config into a popover so the artifact list keeps
// the vertical space. An accent dot marks a non-default (summaries-on) config so
// "collapse" never becomes "hide" — the active mode gates real model cost.
export function SummaryConfig({ selection, onSelectionChange, style, onStyleChange, note, onNoteChange }: Props): JSX.Element {
  const btnRef = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useState(false)
  const active = !isOff(selection) || note.trim().length > 0

  return (
    <>
      <Tooltip
        label="Summary settings"
        description="AI target + depth used to summarize dropped artifacts"
        placement="bottom"
      >
        <button
          ref={btnRef}
          type="button"
          className={s.btn}
          aria-label="Summary settings"
          {...(active ? { 'data-active': '' } : {})}
          {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
          onClick={() => setOpen((v) => !v)}
        >
          <SlidersHorizontal size={14} />
          {active && <span className={s.dot} />}
        </button>
      </Tooltip>
      {open && (
        <SummaryConfigPopover
          anchorEl={btnRef.current}
          selection={selection}
          onSelectionChange={onSelectionChange}
          style={style}
          onStyleChange={onStyleChange}
          note={note}
          onNoteChange={onNoteChange}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  )
}
