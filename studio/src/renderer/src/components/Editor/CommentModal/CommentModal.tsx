import React, { useState, useRef, useEffect } from 'react'
import { X } from 'lucide-react'
import styles from './CommentModal.module.css'

interface Props {
  anchorText: string
  x: number
  y: number
  onAdd: (body: string) => void
  onSendNow: (body: string) => void
  onClose: () => void
}

export function CommentModal({ anchorText, x, y, onAdd, onSendNow, onClose }: Props): JSX.Element {
  const [body, setBody] = useState('')
  const canSubmit = body.trim().length > 0
  const ref = useRef<HTMLDivElement>(null)
  const preview = anchorText.length > 100 ? anchorText.slice(0, 100).trim() + '…' : anchorText.trim()

  // Position below selection, clamped to viewport
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const { width, height } = el.getBoundingClientRect()
    let left = x - width / 2
    let top = y + 10
    left = Math.max(8, Math.min(left, window.innerWidth - width - 8))
    if (top + height > window.innerHeight - 8) top = y - height - 10
    el.style.setProperty('--modal-x', `${left}px`)
    el.style.setProperty('--modal-y', `${top}px`)
  }, [x, y])

  // Dismiss on click outside
  useEffect(() => {
    function onMouseDown(e: MouseEvent): void {
      if (!ref.current?.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', onMouseDown)
    return () => document.removeEventListener('mousedown', onMouseDown)
  }, [onClose])

  return (
    <div ref={ref} className={styles.modal} onMouseDown={(e) => e.stopPropagation()}>
      <div className={styles.header}>
        <span className={styles.title}>Comment</span>
        <button type="button" className={styles.closeBtn} onClick={onClose} aria-label="Close">
          <X size={14} />
        </button>
      </div>

      {anchorText && <div className={styles.anchor}>"{preview}"</div>}

      <textarea
        className={styles.textarea}
        placeholder="Describe the issue or suggestion…"
        value={body}
        onChange={(e) => setBody(e.target.value)}
        rows={4}
        autoFocus
      />

      <div className={styles.actions}>
        <button
          type="button"
          className={styles.sendBtn}
          disabled={!canSubmit}
          onClick={() => { if (canSubmit) onSendNow(body.trim()) }}
        >
          Send to Claude
        </button>
        <button
          type="button"
          className={styles.addBtn}
          disabled={!canSubmit}
          onClick={() => { if (canSubmit) onAdd(body.trim()) }}
        >
          Add comment
        </button>
      </div>
    </div>
  )
}
