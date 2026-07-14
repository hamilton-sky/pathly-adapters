import { useState, useEffect, useCallback } from 'react'
import { useRunnerStore } from '../../../../store/runnerStore'
import { OutputTab } from '../OutputTab'
import styles from './OutputBanner.module.css'

// Compact output affordance for the Pipeline panel. With the pipeline-on-top / grid-below
// layout, the stage output no longer gets its own big band — instead this thin strip sits
// directly under the pipeline and opens the full stage results in a modal, so the global
// engine board stays the panel's main content. Renders nothing until a run produces output
// (mirrors OutputTab's own empty gate); the grid then fills the space.
export function OutputBanner(): JSX.Element | null {
  const stageLog = useRunnerStore((s) => s.stageLog)
  const runHistory = useRunnerStore((s) => s.runHistory)
  const cost = useRunnerStore((s) => s.cost)
  const [open, setOpen] = useState(false)

  const handleKey = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape') setOpen(false)
  }, [])
  useEffect(() => {
    if (!open) return
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [open, handleKey])

  const stageCount = stageLog.length
  const hasOutput = stageCount > 0 || runHistory.length > 0
  if (!hasOutput) return null

  return (
    <>
      <button
        type="button"
        className={styles.banner}
        onClick={() => setOpen(true)}
        {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
        aria-label="Show stage output"
      >
        <span className={styles.label}>Output</span>
        <span className={styles.meta}>
          {stageCount > 0 ? `${stageCount} stage${stageCount !== 1 ? 's' : ''} · ` : ''}
          {`$${cost.toFixed(3)}`}
        </span>
        <span className={styles.hint}>View ▸</span>
      </button>

      {open && (
        <div
          className={styles.backdrop}
          onClick={() => setOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-label="Stage output"
        >
          <div className={styles.panel} onClick={(e) => e.stopPropagation()}>
            <div className={styles.header}>
              <span className={styles.title}>Output</span>
              <button
                type="button"
                className={styles.closeBtn}
                onClick={() => setOpen(false)}
                aria-label="Close"
              >
                ✕
              </button>
            </div>
            <div className={styles.body}>
              <OutputTab />
            </div>
          </div>
        </div>
      )}
    </>
  )
}
