import React from 'react'
import { Plus } from 'lucide-react'
import styles from './InsertZone.module.css'

interface Props {
  afterCellId: string | null
  dragActive: boolean
  isDragging?: boolean
  onDragOver: () => void
  onDrop: (e: React.DragEvent) => void
  onDragLeave: () => void
  onInsert?: () => void
}

export default function InsertZone({
  afterCellId: _afterCellId,
  dragActive,
  isDragging: _isDragging = false,
  onDragOver,
  onDrop,
  onDragLeave,
  onInsert,
}: Props) {
  return (
    <div
      className={`${styles.zone} ${dragActive ? styles.dragActive : ''}`}
      onDragOver={e => { e.preventDefault(); onDragOver() }}
      onDrop={e => { e.preventDefault(); onDrop(e) }}
      onDragLeave={onDragLeave}
    >
      <button
        type="button"
        className={styles.plus}
        aria-label="Insert cell here"
        onClick={onInsert}
      >
        <Plus size={14} />
      </button>
    </div>
  )
}
