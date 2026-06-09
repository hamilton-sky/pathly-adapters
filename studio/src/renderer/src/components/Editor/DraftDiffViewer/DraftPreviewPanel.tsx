import { useState } from 'react'
import type { DiffHunk } from './useDraftDiff'
import MarkdownRenderer from '../../shared/MarkdownRenderer/MarkdownRenderer'
import styles from './DraftPreviewPanel.module.css'

interface Props {
  content: string
  changedHunks: DiffHunk[]
}

type Mode = 'result' | 'changes'

export function DraftPreviewPanel({ content, changedHunks }: Props) {
  const [mode, setMode] = useState<Mode>('result')

  const accepted = changedHunks.filter((h) => h.status !== 'unchanged' && h.accepted)

  return (
    <div className={styles.panel}>
      <div className={styles.panelHeader} role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'result'}
          className={`${styles.tab} ${mode === 'result' ? styles.tabActive : ''}`}
          onClick={() => setMode('result')}
        >
          Result
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'changes'}
          className={`${styles.tab} ${mode === 'changes' ? styles.tabActive : ''}`}
          onClick={() => setMode('changes')}
        >
          Changes
        </button>
      </div>

      <div className={styles.body}>
        {mode === 'result' ? (
          <MarkdownRenderer content={content} />
        ) : accepted.length === 0 ? (
          <div className={styles.empty}>No changes selected</div>
        ) : (
          accepted.map((hunk) => (
            <div key={hunk.id} className={styles.changeSection}>
              <div className={styles.changeHeading}>
                {hunk.heading === '__preamble__' ? 'Preamble' : hunk.heading}
              </div>
              <pre className={styles.changeText}>{hunk.draftContent ?? ''}</pre>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
