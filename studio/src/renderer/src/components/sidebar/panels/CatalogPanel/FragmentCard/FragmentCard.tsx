import React from 'react'
import styles from './FragmentCard.module.css'

interface Props {
  name: string
  description: string
  category: string
  requires?: string
}

const CATEGORY_CLASS: Record<string, string> = {
  core: styles.badgeCore,
  flow: styles.badgeFlow,
  integration: styles.badgeIntegration,
}

export default function FragmentCard({ name, description, category, requires }: Props) {
  return (
    <div
      className={styles.card}
      draggable
      onDragStart={e => {
        e.dataTransfer.setData('fragment-name', name)
        e.dataTransfer.effectAllowed = 'copy'
      }}
    >
      <div className={styles.header}>
        <span className={styles.name}>{name}</span>
        <span className={`${styles.badge} ${CATEGORY_CLASS[category] ?? ''}`}>
          {category.toUpperCase()}
        </span>
      </div>
      {description && (
        <div className={styles.description}>{description}</div>
      )}
      {requires && (
        <div className={styles.requires}>requires: {requires}</div>
      )}
    </div>
  )
}
