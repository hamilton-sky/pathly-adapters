import { useState, useEffect, useCallback } from 'react'
import { marked } from 'marked'
import type { StageLogEntry } from '../../store/runnerStore'
import styles from './StageModal.module.css'

interface Props {
  entry: StageLogEntry
  onClose: () => void
}

export function StageModal({ entry, onClose }: Props): JSX.Element {
  const [resultView, setResultView] = useState<'raw' | 'preview'>('preview')
  const [promptOpen, setPromptOpen] = useState(false)
  const [promptView, setPromptView] = useState<'raw' | 'preview'>('raw')

  const handleKey = useCallback((e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }, [onClose])
  useEffect(() => {
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [handleKey])

  const adapterClass = entry.adapter === 'claude' ? styles.adapterClaude : entry.adapter === 'codex' ? styles.adapterCodex : entry.adapter === 'agy' ? styles.adapterAgy : ''
  const dotClass = entry.exitCode === null ? styles.dotPending : entry.exitCode === 0 ? styles.dotOk : styles.dotFail

  return (
    <div className={styles.backdrop} onClick={onClose} role="dialog" aria-modal="true" aria-label={`${entry.stage} details`}>
      <div className={styles.panel} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <span className={styles.stageName}>{entry.stage}</span>
          {entry.adapter && <span className={`${styles.adapterPill} ${adapterClass}`}>{entry.adapter}</span>}
          <span className={dotClass} />
          <div className={styles.headerMeta}>
            {entry.durationMs != null && <span>{(entry.durationMs / 1000).toFixed(1)}s</span>}
            {entry.costUsd != null && <span>${entry.costUsd.toFixed(3)}</span>}
          </div>
          <button type="button" className={styles.closeBtn} onClick={onClose} aria-label="Close">✕</button>
        </div>

        <div className={styles.body}>
          {entry.result != null ? (
            <>
              <div className={styles.sectionRow}>
                <span className={styles.sectionLabel}>Result</span>
                <div className={styles.viewBar} role="group" aria-label="Result view mode">
                  <button type="button" className={resultView === 'preview' ? `${styles.viewBtn} ${styles.viewBtnActive}` : styles.viewBtn} onClick={() => setResultView('preview')}>Preview</button>
                  <button type="button" className={resultView === 'raw' ? `${styles.viewBtn} ${styles.viewBtnActive}` : styles.viewBtn} onClick={() => setResultView('raw')}>Raw</button>
                </div>
              </div>
              {resultView === 'raw'
                ? <div className={styles.resultBox}>{entry.result}</div>
                : <div className={styles.resultPreview} dangerouslySetInnerHTML={{ __html: marked(entry.result) as string }} />
              }
            </>
          ) : (
            <p className={styles.muted}>No result captured</p>
          )}

          {entry.inputTokens != null && (
            <div className={styles.tokenRow}>
              in {entry.inputTokens?.toLocaleString()} · out {entry.outputTokens?.toLocaleString()} · cache↑ {entry.cacheCreateTokens?.toLocaleString()} · cache↓ {entry.cacheReadTokens?.toLocaleString()}
            </div>
          )}

          {entry.prompt != null && (
            <>
              <div className={styles.sectionRow}>
                <button type="button" className={styles.promptToggle} onClick={() => setPromptOpen((v) => !v)} {...(promptOpen ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}>
                  {promptOpen ? 'Hide prompt ▲' : 'Show prompt ▾'}
                </button>
                {promptOpen && (
                  <div className={styles.viewBar} role="group" aria-label="Prompt view mode">
                    <button type="button" className={promptView === 'raw' ? `${styles.viewBtn} ${styles.viewBtnActive}` : styles.viewBtn} onClick={() => setPromptView('raw')}>Raw</button>
                    <button type="button" className={promptView === 'preview' ? `${styles.viewBtn} ${styles.viewBtnActive}` : styles.viewBtn} onClick={() => setPromptView('preview')}>Preview</button>
                  </div>
                )}
              </div>
              {promptOpen && promptView === 'raw' && <div className={styles.promptBox}>{entry.prompt}</div>}
              {promptOpen && promptView === 'preview' && <div className={styles.promptPreview} dangerouslySetInnerHTML={{ __html: marked(entry.prompt) as string }} />}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
