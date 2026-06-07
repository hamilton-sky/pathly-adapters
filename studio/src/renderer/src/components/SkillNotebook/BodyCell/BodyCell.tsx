import React, { useState } from 'react'
import {
  Lock, ChevronUp, ChevronDown, Pencil, MoreHorizontal,
} from 'lucide-react'
import styles from './BodyCell.module.css'

interface Props {
  heading: string
  content: string
}

export default function BodyCell({ heading, content }: Props) {
  const [expanded, setExpanded] = useState(false)
  const lines = content.split('\n')
  const isLong = lines.length > 3
  const preview = isLong && !expanded ? lines.slice(0, 3).join('\n') : content

  return (
    <div className={styles.cell}>
      <div className={styles.cellHead}>
        <span className={styles.title}>{heading}</span>
        <span className={styles.typeBadge}>body</span>
        <Lock size={12} className={styles.lock} />
        <div className={styles.actions}>
          <button type="button" className={styles.actionBtn} aria-label="Move up"><ChevronUp size={13} /></button>
          <button type="button" className={styles.actionBtn} aria-label="Move down"><ChevronDown size={13} /></button>
          <button type="button" className={styles.actionBtn} aria-label="Edit"><Pencil size={13} /></button>
          <button type="button" className={styles.actionBtn} aria-label="More"><MoreHorizontal size={13} /></button>
        </div>
      </div>
      <div className={styles.cellBody}>
        <pre className={styles.content}>{preview}</pre>
        {isLong && (
          <button
            type="button"
            className={styles.toggle}
            onClick={() => setExpanded(e => !e)}
          >
            {expanded ? '▴ Collapse' : '▾ Show full content'}
          </button>
        )}
      </div>
    </div>
  )
}
