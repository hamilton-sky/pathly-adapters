import React, { useState } from 'react'
import { Lock } from 'lucide-react'
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
      <div className={styles.header}>
        <span className={styles.heading}>{heading}</span>
        <Lock size={12} className={styles.lock} />
      </div>
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
  )
}
