import { useRef, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { useFocusTrap } from '../../../hooks/useFocusTrap'
import s from './NewFeatureModal.module.css'

export type DefaultExecutor = 'single' | 'loop' | 'team'

export interface NewFeatureModalProps {
  onCancel: () => void
  onCreate: (topic: string, description: string, executor: DefaultExecutor) => void
}

function slugify(raw: string): string {
  return raw
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

const EXECUTOR_OPTIONS: Array<{ value: DefaultExecutor; label: string }> = [
  { value: 'single', label: 'Single agent' },
  { value: 'loop',   label: 'Loop' },
  { value: 'team',   label: 'Team' },
]

export function NewFeatureModal({ onCancel, onCreate }: NewFeatureModalProps) {
  const boxRef = useRef<HTMLDivElement>(null)
  useFocusTrap(boxRef)

  const [title, setTitle]       = useState('')
  const [desc, setDesc]         = useState('')
  const [executor, setExecutor] = useState<DefaultExecutor>('team')

  const topic = slugify(title)
  const canCreate = topic.length > 0

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
    onCreate(topic, desc.trim(), executor)
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
        aria-labelledby="new-feature-title"
        className={s.box}
      >
        <p id="new-feature-title" className={s.heading}>New feature</p>

        <form onSubmit={handleSubmit} className={s.form}>
          <label className={s.label} htmlFor="nf-title">Title <span className={s.req}>*</span></label>
          <input
            id="nf-title"
            type="text"
            className={s.input}
            placeholder="e.g. RTK token killer"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            autoComplete="off"
          />
          {title.length > 0 && (
            <p className={s.slug}>ID: <code>{topic || '…'}</code></p>
          )}

          <label className={s.label} htmlFor="nf-desc">Description <span className={s.opt}>(optional)</span></label>
          <textarea
            id="nf-desc"
            className={s.textarea}
            placeholder="What is this feature about?"
            value={desc}
            onChange={(e) => setDesc(e.target.value)}
            rows={3}
          />

          <label className={s.label} htmlFor="nf-executor">Default executor</label>
          <select
            id="nf-executor"
            className={s.select}
            value={executor}
            onChange={(e) => setExecutor(e.target.value as DefaultExecutor)}
          >
            {EXECUTOR_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>

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
