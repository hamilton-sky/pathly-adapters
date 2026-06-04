import React from 'react'
import styles from './PreviewSection.module.css'

interface Props {
  heading: string
  content: string
  origin: 'body' | 'fragment'
}

export default function PreviewSection({ heading, content, origin }: Props) {
  const highlighted = content.replace(
    /<([^>]+)>/g,
    '<span class="var-highlight">$1</span>'
  )

  return (
    <div className={styles.section}>
      <div className={styles.header}>
        <span className={styles.heading}>{heading.toUpperCase()}</span>
        <span className={`${styles.badge} ${origin === 'body' ? styles.badgeBody : styles.badgeFrag}`}>
          {origin === 'body' ? 'BODY' : 'FRAG'}
        </span>
      </div>
      <div
        className={styles.content}
        dangerouslySetInnerHTML={{ __html: highlighted }}
      />
    </div>
  )
}
