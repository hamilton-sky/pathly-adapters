import React from 'react'
import MarkdownRenderer from '../../../shared/MarkdownRenderer/MarkdownRenderer'
import styles from './PreviewSection.module.css'

interface Props {
  heading: string
  content: string
}

export default function PreviewSection({ heading, content }: Props) {
  return (
    <div className={styles.section}>
      <div className={styles.header}>
        <span className={styles.heading}>{heading.toUpperCase()}</span>
      </div>
      <MarkdownRenderer content={content} className={styles.content} />
    </div>
  )
}
