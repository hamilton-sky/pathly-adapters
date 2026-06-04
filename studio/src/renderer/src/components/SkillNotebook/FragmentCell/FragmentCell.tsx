import React, { useState, useEffect } from 'react'
import { GripVertical, X } from 'lucide-react'
import styles from './FragmentCell.module.css'
import { useSkillNotebookStore } from '../../../store/skillNotebookStore'

interface Props {
  id: string
  fragmentName: string
  category: string
  description: string
  isNew?: boolean
}

const CATEGORY_CLASS: Record<string, string> = {
  core: styles.badgeCore,
  flow: styles.badgeFlow,
  integration: styles.badgeIntegration,
}

export default function FragmentCell({ id, fragmentName, category, description, isNew = false }: Props) {
  const removeCell = useSkillNotebookStore(s => s.removeCell)
  const [showNew, setShowNew] = useState(isNew)

  useEffect(() => {
    if (!showNew) return
    const t = setTimeout(() => setShowNew(false), 150)
    return () => clearTimeout(t)
  }, [showNew])

  return (
    <div className={`${styles.cell} ${showNew ? styles.cellNew : ''}`}>
      <div
        className={styles.grip}
        draggable
        onDragStart={e => {
          e.dataTransfer.setData('cell-id', id)
          e.dataTransfer.effectAllowed = 'move'
        }}
      >
        <GripVertical size={14} />
      </div>
      <div className={styles.body}>
        <div className={styles.header}>
          <span className={styles.name}>{fragmentName}</span>
          <span className={`${styles.badge} ${CATEGORY_CLASS[category] ?? ''}`}>
            {category.toUpperCase()}
          </span>
        </div>
        {description && (
          <div className={styles.description}>{description}</div>
        )}
      </div>
      <button
        type="button"
        className={styles.remove}
        onClick={() => removeCell(id)}
        title="Remove fragment"
        aria-label="Remove fragment"
      >
        <X size={12} />
      </button>
    </div>
  )
}
