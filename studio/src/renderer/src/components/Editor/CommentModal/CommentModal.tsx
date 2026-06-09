import React, { useState, useRef, useEffect } from 'react'
import { X } from 'lucide-react'
import { Tooltip } from '../../ui'
import { COMMENT_COLORS } from '../useComments'
import type { CommentColor } from '../useComments'
import styles from './CommentModal.module.css'

interface Props {
  anchorText: string
  x: number
  y: number
  initialBody?: string
  onAdd: (body: string, color: CommentColor) => void
  onSendNow: (body: string, color: CommentColor) => void
  onDraftChange: (body: string) => void
  onClose: () => void
  onCancel: () => void
}

export function CommentModal({ anchorText, x, y, initialBody, onAdd, onSendNow, onDraftChange, onClose, onCancel }: Props): JSX.Element {
  const [body, setBody] = useState(initialBody ?? '')
  const [selectedColor, setSelectedColor] = useState<CommentColor>('yellow')
  const canSubmit = body.trim().length > 0
  const ref = useRef<HTMLDivElement>(null)
  const preview = anchorText.length > 120 ? anchorText.slice(0, 120).trimEnd() + '…' : anchorText.trim()

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const { width, height } = el.getBoundingClientRect()
    let left = x - width / 2
    let top = y + 12
    left = Math.max(8, Math.min(left, window.innerWidth - width - 8))
    if (top + height > window.innerHeight - 8) top = y - height - 12
    el.style.setProperty('--modal-x', `${left}px`)
    el.style.setProperty('--modal-y', `${top}px`)
  }, [x, y])

  // Update accent color when selected swatch changes
  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.setProperty('--modal-accent', `var(--comment-${selectedColor}-border)`)
  }, [selectedColor])

  useEffect(() => {
    function onMouseDown(e: MouseEvent): void {
      if (!ref.current?.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', onMouseDown)
    return () => document.removeEventListener('mousedown', onMouseDown)
  }, [onClose])

  function handleCancel(): void {
    setSelectedColor('yellow')
    onCancel()
  }

  return (
    <div ref={ref} className={styles.modal} onMouseDown={(e) => e.stopPropagation()}>
      <div className={styles.header}>
        <span className={styles.title}>Comment</span>
        <button type="button" className={styles.closeBtn} onClick={handleCancel} aria-label="Close">
          <X size={14} />
        </button>
      </div>

      {anchorText && <div className={styles.anchor}>"{preview}"</div>}

      <div className={styles.swatchRow}>
        <span className={styles.srOnly}>Comment color</span>
        {COMMENT_COLORS.map((color) => (
          <Tooltip key={color} label={color.charAt(0).toUpperCase() + color.slice(1)} placement="top">
            <button
              type="button"
              className={`${styles.swatch} ${selectedColor === color ? styles.swatchSelected : ''}`}
              aria-label={`Set comment color to ${color}`}
              aria-pressed={selectedColor === color}
              onClick={() => setSelectedColor(color)}
              data-color={color}
            />
          </Tooltip>
        ))}
      </div>

      <textarea
        className={styles.textarea}
        placeholder="Describe the issue or suggestion…"
        value={body}
        onChange={(e) => { setBody(e.target.value); onDraftChange(e.target.value) }}
        rows={4}
        autoFocus
      />

      <div className={styles.actions}>
        <button
          type="button"
          className={styles.sendBtn}
          disabled={!canSubmit}
          onClick={() => { if (canSubmit) onSendNow(body.trim(), selectedColor) }}
        >
          Send to Claude
        </button>
        <button
          type="button"
          className={styles.addBtn}
          disabled={!canSubmit}
          onClick={() => { if (canSubmit) onAdd(body.trim(), selectedColor) }}
        >
          Add comment
        </button>
      </div>
    </div>
  )
}
