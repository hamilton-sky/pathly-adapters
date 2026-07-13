// One analysis report card: lens badge / date·engine header (click to expand), the rendered
// markdown report when expanded, and Add-to-board / Copy / Delete actions. "Add to board"
// posts the report as a comms artifact (the card stays); a check marks ones already on the
// board. Mirrors DiagramCard, but renders markdown inline instead of a diagram thumbnail.
//
// Path assumes: src/components/MarkdownEditor/AnalysisGalleryPanel/AnalysisCard/AnalysisCard.tsx

import React, { useState } from 'react'
import { ChevronDown, ChevronRight, Copy, Check, Trash2 } from 'lucide-react'
import type { AnalysisEntry } from '../../analysisTypes'
import { MarkdownPreview } from '../../../Editor/MarkdownPreview'
import { useToastStore } from '../../../../store/toastStore'
import AddToBoardButton, {
  type BoardTarget,
  type BoardTargetOption,
} from '../../../shared/AddToBoardButton/AddToBoardButton'
import { formatDateShort } from '../../../../utils/timestamp'
import styles from './AnalysisCard.module.css'

interface Props {
  entry: AnalysisEntry
  onAddToBoard: (entry: AnalysisEntry, target: BoardTarget) => void
  /** Board destinations for the Add-to-board dropdown (Global / Project / features). */
  targets: BoardTargetOption[]
  onDelete: (entry: AnalysisEntry) => void
  /** Expanded on mount — the gallery expands the newest report. */
  defaultExpanded?: boolean
}

export default function AnalysisCard({ entry, onAddToBoard, targets, onDelete, defaultExpanded }: Props) {
  const [expanded, setExpanded] = useState(Boolean(defaultExpanded))
  const [copied, setCopied] = useState(false)
  const onBoard = Boolean(entry.board)

  function handleCopy() {
    void navigator.clipboard.writeText(entry.content).then(
      () => {
        setCopied(true)
        setTimeout(() => setCopied(false), 1500)
      },
      () => useToastStore.getState().push('Could not copy report', 'error', { category: 'agent_done' }),
    )
  }

  return (
    <div className={styles.card}>
      <button
        type="button"
        className={styles.head}
        onClick={() => setExpanded((v) => !v)}
        {...(expanded ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
      >
        {expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        <span className={styles.badge} data-lens={entry.lens}>
          <span className={styles.dot} />
          {entry.title || entry.lens}
        </span>
        <span className={styles.spacer} />
        <span className={styles.meta}>
          {formatDateShort(entry.createdAt)} · {entry.engine}
        </span>
      </button>

      {expanded && (
        <div className={styles.report}>
          <MarkdownPreview content={entry.content} />
        </div>
      )}

      <div className={styles.actions}>
        <AddToBoardButton
          onBoard={onBoard}
          targets={targets}
          onPick={(t) => onAddToBoard(entry, t)}
        />
        <button
          type="button"
          className={styles.iconBtn}
          onClick={handleCopy}
          aria-label="Copy report markdown"
          title="Copy report markdown"
        >
          {copied ? <Check size={12} /> : <Copy size={12} />}
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
