import React, { useState } from 'react'
import { X } from 'lucide-react'
import styles from './CommentModal.module.css'

interface Props {
  anchorText: string
  onAdd: (body: string) => void
  onSendNow: (body: string) => void
  onClose: () => void
}

export function CommentModal({ anchorText, onAdd, onSendNow, onClose }: Props): JSX.Element {
  const [body, setBody] = useState('')
  const canSubmit = body.trim().length > 0
  const preview = anchorText.length > 120
    ? anchorText.slice(0, 120).trim() + '…'
    : anchorText.trim()

  return (
    <div className={styles.overlay} onMouseDown={onClose}>
      <div className={styles.modal} onMouseDown={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <span className={styles.title}>Comment</span>
          <button type="button" className={styles.closeBtn} onClick={onClose} aria-label="Close">
            <X size={14} />
          </button>
        </div>

        {anchorText && (
          <div className={styles.anchor}>"{preview}"</div>
        )}

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
    </div>
  )
}
