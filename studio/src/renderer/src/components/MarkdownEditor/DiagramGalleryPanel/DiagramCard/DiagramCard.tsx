// One diagram card: style badge / status / date·engine header, a clamped render,
// and View / Regenerate / Delete actions.
//
// Path assumes: src/components/MarkdownEditor/DiagramGalleryPanel/DiagramCard/DiagramCard.tsx

import React from 'react'
import { Eye, RefreshCw, Trash2 } from 'lucide-react'
import type { DiagramEntry } from '../../diagramTypes'
import DiagramRender from '../DiagramRender/DiagramRender'
import styles from './DiagramCard.module.css'

interface Props {
  entry: DiagramEntry
  onView: (entry: DiagramEntry) => void
  onRegenerate: (entry: DiagramEntry) => void
  onDelete: (entry: DiagramEntry) => void
  /** Regenerate is disabled while another run for this file is in flight. */
  busy?: boolean
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export default function DiagramCard({ entry, onView, onRegenerate, onDelete, busy }: Props) {
  return (
    <div className={styles.card}>
      <div className={styles.head}>
        <span className={styles.badge} data-style={entry.style}>
          <span className={styles.dot} />
          {entry.style}
        </span>
        {entry.status === 'kept' && <span className={styles.status}>ok</span>}
        <span className={styles.spacer} />
        <span className={styles.meta}>
          {formatDate(entry.createdAt)} · {entry.engine}
        </span>
      </div>

      <button type="button" className={styles.render} onClick={() => onView(entry)} aria-label={`View ${entry.title}`}>
        <DiagramRender entry={entry} mode="card" />
      </button>

      <div className={styles.actions}>
        <button type="button" className={styles.viewBtn} onClick={() => onView(entry)}>
          <Eye size={12} />
          View
        </button>
        <button
          type="button"
          className={styles.iconBtn}
          onClick={() => onRegenerate(entry)}
          disabled={busy}
          aria-label="Regenerate"
          title="Regenerate"
        >
          <RefreshCw size={12} />
        </button>
        <button
          type="button"
          className={styles.deleteBtn}
          onClick={() => onDelete(entry)}
          aria-label="Delete"
          title="Delete"
        >
          <Trash2 size={12} />
        </button>
      </div>
    </div>
  )
}
