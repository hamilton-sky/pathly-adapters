import { useState } from 'react'
import { Pencil, Check, X } from 'lucide-react'
import { Tooltip } from '../../../ui'
import MarkdownRenderer from '../../../../components/shared/MarkdownRenderer/MarkdownRenderer'
import s from './GoalsView.module.css'

interface Props {
  text: string
  onSave: (text: string) => void
}

// The goal title — rendered as markdown, with an inline edit mode (pencil → textarea
// → save/cancel). Saving keeps the goal id, so its task links survive a rename.
export function EditableGoalTitle({ text, onSave }: Props): JSX.Element {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(text)

  if (editing) {
    const save = (): void => {
      const t = draft.trim()
      if (t && t !== text) onSave(t)
      setEditing(false)
    }
    const cancel = (): void => { setDraft(text); setEditing(false) }
    return (
      <div className={s.titleEdit}>
        <textarea
          className={s.titleInput}
          value={draft}
          autoFocus
          onChange={(e) => setDraft(e.currentTarget.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); save() }
            if (e.key === 'Escape') { e.preventDefault(); cancel() }
          }}
        />
        <button type="button" className={s.titleIconBtn} onClick={save} aria-label="Save goal title"><Check size={13} /></button>
        <button type="button" className={s.titleIconBtn} onClick={cancel} aria-label="Cancel edit"><X size={13} /></button>
      </div>
    )
  }

  return (
    <div className={s.titleView}>
      <MarkdownRenderer content={text} className={s.goalText} />
      <Tooltip label="Edit goal" placement="top">
        <button
          type="button"
          className={s.titleEditBtn}
          onClick={() => { setDraft(text); setEditing(true) }}
          aria-label="Edit goal title"
        >
          <Pencil size={12} />
        </button>
      </Tooltip>
    </div>
  )
}
