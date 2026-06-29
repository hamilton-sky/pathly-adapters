import { useEffect, useState } from 'react'
import { Check, X } from 'lucide-react'
import MarkdownRenderer from '../../../../shared/MarkdownRenderer/MarkdownRenderer'
import s from './GoalCard.module.css'

interface Props {
  text: string
  editing: boolean
  onSave: (text: string) => void
  onCancel: () => void
}

// The goal title — markdown when viewing, a textarea when editing. `editing` is controlled by
// the header (so the edit pencil can sit in the shared action group with copy/delete). Saving
// keeps the goal id, so its task links survive a rename.
export function EditableGoalTitle({ text, editing, onSave, onCancel }: Props): JSX.Element {
  const [draft, setDraft] = useState(text)
  useEffect(() => { if (editing) setDraft(text) }, [editing, text])

  if (editing) {
    const save = (): void => {
      const t = draft.trim()
      if (t && t !== text) onSave(t)
      onCancel()
    }
    return (
      <div className={s.titleEdit}>
        <textarea
          className={s.titleInput}
          value={draft}
          autoFocus
          onChange={(e) => setDraft(e.currentTarget.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); save() }
            if (e.key === 'Escape') { e.preventDefault(); onCancel() }
          }}
        />
        <button type="button" className={s.titleIconBtn} onClick={save} aria-label="Save goal title"><Check size={13} /></button>
        <button type="button" className={s.titleIconBtn} onClick={onCancel} aria-label="Cancel edit"><X size={13} /></button>
      </div>
    )
  }

  return (
    <div className={s.titleView}>
      <div className={s.goalText} title={text}>
        <MarkdownRenderer content={text} className={s.goalMd} />
      </div>
    </div>
  )
}
