import React from 'react'
import styles from './InsertZone.module.css'

interface Props {
  afterCellId: string | null
  dragActive: boolean
  isDragging?: boolean
  onDragOver: () => void
  onDrop: (e: React.DragEvent) => void
  onDragLeave: () => void
}

export default function InsertZone({ afterCellId: _afterCellId, dragActive, isDragging = false, onDragOver, onDrop, onDragLeave }: Props) {
  return (
    <div
      className={`${styles.zone} ${dragActive || isDragging ? styles.active : ''}`}
      onDragOver={e => {
        e.preventDefault()
        onDragOver()
      }}
      onDrop={e => {
        e.preventDefault()
        onDrop(e)
      }}
      onDragLeave={onDragLeave}
    >
      {dragActive && <span className={styles.label}>+ Drop here</span>}
    </div>
  )
}
