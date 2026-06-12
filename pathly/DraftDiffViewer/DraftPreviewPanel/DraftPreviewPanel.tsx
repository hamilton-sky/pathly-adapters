import { useState } from 'react'
import type { DiffHunk } from '../useDraftDiff'
import { DiffCodeBlock } from '../DiffCodeBlock/DiffCodeBlock'
// Local minimal markdown renderer — in the Studio app you can swap this for the
// shared one (../../shared/MarkdownRenderer/MarkdownRenderer).
import MarkdownRenderer from '../MarkdownRenderer/MarkdownRenderer'
import styles from './DraftPreviewPanel.module.css'

interface Props {
  content: string
  changedHunks: DiffHunk[]
}

type Mode = 'result' | 'changes' | 'diff'

function displayHeading(heading: string): string {
  return heading === '__preamble__' ? 'Preamble' : heading
}

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
              <div key={hunk.id} className={styles.section}>
                <div className={styles.sectionHeading}>{displayHeading(hunk.heading)}</div>
                <DiffCodeBlock original={hunk.originalContent} draft={hunk.draftContent} />
              </div>
            ))
          )
        ) : accepted.length === 0 ? (
          <div className={styles.empty}>No changes selected</div>
        ) : (
          accepted.map((hunk) => (
            <div key={hunk.id} className={styles.section}>
              <div className={styles.sectionHeading}>{displayHeading(hunk.heading)}</div>
              <pre className={styles.changeText}>{hunk.draftContent ?? ''}</pre>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
