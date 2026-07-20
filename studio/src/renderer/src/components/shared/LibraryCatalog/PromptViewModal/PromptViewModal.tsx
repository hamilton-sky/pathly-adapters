import { X } from 'lucide-react'
import s from './PromptViewModal.module.css'

interface Props {
  title: string
  body: string
  onClose: () => void
}

// Read-only viewer for an app-shipped builtin system-prompt. Builtins are client constants with
// no file, so they can't open in the MD editor like a user prompt — this lets you still read
// exactly what the preset sends. (Your own system-prompts are files: use "Open to edit" instead.)
export function PromptViewModal({ title, body, onClose }: Props): JSX.Element {
  return (
    <div className={s.backdrop} onClick={onClose}>
      <div
        className={s.modal}
        role="dialog"
        aria-modal="true"
        aria-label={`View ${title}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className={s.header}>
          <span className={s.title}>{title}</span>
          <span className={s.badge}>built-in · read-only</span>
          <button type="button" className={s.closeBtn} onClick={onClose} aria-label="Close">
            <X size={15} />
          </button>
        </div>
        <pre className={s.body}>{body}</pre>
      </div>
    </div>
  )
}
