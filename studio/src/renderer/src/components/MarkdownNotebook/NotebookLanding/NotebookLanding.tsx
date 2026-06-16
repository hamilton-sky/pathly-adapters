import React from 'react'
import { BookOpen, FileCode, GitCompare } from 'lucide-react'
import styles from './NotebookLanding.module.css'

const FEATURES = [
  {
    icon: BookOpen,
    title: 'Visual editor',
    body: 'Drag and reorder sections, edit cells inline, preview the assembled document live.',
  },
  {
    icon: FileCode,
    title: 'Source editor',
    body: 'Raw markdown with syntax highlighting, split view, and Ctrl+S to save.',
  },
  {
    icon: GitCompare,
    title: 'Draft review',
    body: 'When an agent edits a document, compare changes inline and accept or discard.',
  },
] as const

export default function NotebookLanding() {
  return (
    <div className={styles.root}>
      {/* Ambient glow — decorative only */}
      <div className={styles.glow} aria-hidden="true" />

      <div className={styles.hero}>
        <div className={styles.iconRing}>
          <BookOpen size={30} />
        </div>
        <div className={styles.heroText}>
          <h2 className={styles.title}>Markdown Notebook</h2>
          <p className={styles.subtitle}>Your workspace for reading and editing any markdown file</p>
        </div>
      </div>

      <div className={styles.cards}>
        {FEATURES.map(({ icon: Icon, title, body }, i) => (
          <div
            key={title}
            className={styles.card}
            style={{ '--delay': `${260 + i * 110}ms` } as React.CSSProperties}
          >
            <div className={styles.cardIconWrap}>
              <Icon size={16} />
            </div>
            <strong className={styles.cardTitle}>{title}</strong>
            <p className={styles.cardBody}>{body}</p>
          </div>
        ))}
      </div>

      <div className={styles.cta}>
        <span className={styles.ctaArrow}>←</span>
        <span className={styles.ctaText}>
          Open any <code className={styles.ctaCode}>.md</code> file from the Files sidebar
        </span>
      </div>
    </div>
  )
}
