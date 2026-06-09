import { useState } from 'react'
import type { DiffHunk } from './useDraftDiff'
import { DiffCodeBlock } from './DiffCodeBlock'
import MarkdownRenderer from '../../shared/MarkdownRenderer/MarkdownRenderer'
import styles from './DraftPreviewPanel.module.css'

interface Props {
  content: string
  changedHunks: DiffHunk[]
}

type Mode = 'result' | 'changes' | 'diff'

export function DraftPreviewPanel({ content, changedHunks }: Props) {
  const [mode, setMode] = useState<Mode>('result')

  const accepted = changedHunks.filter((h) => h.status !== 'unchanged' && h.accepted)
  const changed = changedHunks.filter((h) => h.status !== 'unchanged')

  return (
    <div className={styles.panel}>
      <div className={styles.panelHeader} role="tablist">
        {(['result', 'changes', 'diff'] as const).map((m) => (
          <button
            key={m}
            type="button"
            role="tab"
            aria-selected={mode === m}
            className={`${styles.tab} ${mode === m ? styles.tabActive : ''}`}
            onClick={() => setMode(m)}
          >
            {m === 'result' ? 'Result' : m === 'changes' ? 'Changes' : 'Diff'}
          </button>
        ))}
      </div>

      <div className={styles.body}>
        {mode === 'result' ? (
          <MarkdownRenderer content={content} />
        ) : mode === 'diff' ? (
          changed.length === 0 ? (
            <div className={styles.empty}>No changes to diff</div>
          ) : (
            changed.map((hunk) => (
              <div key={hunk.id} className={styles.diffSection}>
                <div className={styles.diffHeading}>
                  {hunk.heading === '__preamble__' ? 'Preamble' : hunk.heading}
                </div>
                <DiffCodeBlock
                  original={hunk.originalContent}
                  draft={hunk.draftContent}
                />
              </div>
            ))
          )
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
