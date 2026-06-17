import { useRef, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { useFocusTrap } from '../../../../hooks/useFocusTrap'
import s from '../../../CommandCenter/NewFeatureModal/NewFeatureModal.module.css'

export interface NewGoalModalProps {
  onCancel: () => void
  onCreate: (text: string) => void
}

// Create-goal dialog — same shell as the New feature modal (Title + optional
// Description), minus the slug/executor. Submitting posts a type='goal' message;
// the goal then offers Decompose → Run. Title is the goal statement; a description,
// if given, is appended as a second paragraph.
export function NewGoalModal({ onCancel, onCreate }: NewGoalModalProps) {
  const boxRef = useRef<HTMLDivElement>(null)
  useFocusTrap(boxRef)

  const [title, setTitle] = useState('')
  const [desc, setDesc]   = useState('')

  const canCreate = title.trim().length > 0

  useEffect(() => {
    function onKey(e: KeyboardEvent): void {
      if (e.key === 'Escape') onCancel()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onCancel])

  function handleSubmit(e: React.FormEvent): void {
    e.preventDefault()
    if (!canCreate) return
    const d = desc.trim()
    onCreate(d ? `${title.trim()}\n\n${d}` : title.trim())
  }

  return createPortal(
    <div
      className={s.overlay}
      onClick={(e) => { if (e.target === e.currentTarget) onCancel() }}
    >
      <div
        ref={boxRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-goal-title"
        className={s.box}
      >
        <p id="new-goal-title" className={s.heading}>New goal</p>

        <form onSubmit={handleSubmit} className={s.form}>
          <label className={s.label} htmlFor="ng-title">Goal <span className={s.req}>*</span></label>
          <input
            id="ng-title"
            type="text"
            className={s.input}
            placeholder="e.g. Add OAuth login"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            autoComplete="off"
          />

          <label className={s.label} htmlFor="ng-desc">Details <span className={s.opt}>(optional)</span></label>
          <textarea
            id="ng-desc"
            className={s.textarea}
            placeholder="Any context the planner should know before decomposing?"
            value={desc}
            onChange={(e) => setDesc(e.target.value)}
            rows={3}
          />

          <div className={s.actions}>
            <button type="button" className={s.cancel} onClick={onCancel}>Cancel</button>
            <button type="submit" className={s.create} disabled={!canCreate}>Create</button>
          </div>
        </form>
      </div>
    </div>,
    document.body,
  )
}
