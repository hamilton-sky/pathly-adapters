import { useState, type KeyboardEvent } from 'react'
import { Check, X } from 'lucide-react'
import s from './TaskEditor.module.css'

interface Props {
  initialText: string
  onSave: (text: string) => void
  onCancel: () => void
}

// Inline task-text editor: a textarea + save/cancel. Ctrl/⌘+Enter saves, Escape cancels.
// Extracted from TaskCard so the card stays a lean display component. Saving no-ops when the
// text is unchanged (falls through to cancel) so an accidental edit doesn't touch the board.
export function TaskEditor({ initialText, onSave, onCancel }: Props): JSX.Element {
  const [draft, setDraft] = useState(initialText)
  const trimmed = draft.trim()
  const canSave = trimmed.length > 0

  function save(): void {
    if (canSave && trimmed !== initialText.trim()) onSave(trimmed)
    else onCancel()
  }
  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>): void {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); save() }
    else if (e.key === 'Escape') { e.preventDefault(); onCancel() }
  }

  return (
    <div className={s.editor}>
      <textarea
        className={s.textarea}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={onKeyDown}
        aria-label="Edit task text"
        autoFocus
        rows={Math.min(14, Math.max(3, draft.split('\n').length + 1))}
      />
      <div className={s.actions}>
        <span className={s.hint}>Ctrl/⌘+Enter to save · Esc to cancel</span>
        <button type="button" className={s.btn} onClick={onCancel} aria-label="Cancel edit">
          <X size={13} />
        </button>
        <button
          type="button"
          className={s.btn}
          data-variant="save"
          onClick={save}
          disabled={!canSave}
          aria-label="Save task"
        >
          <Check size={13} />
        </button>
      </div>
    </div>
  )
}
