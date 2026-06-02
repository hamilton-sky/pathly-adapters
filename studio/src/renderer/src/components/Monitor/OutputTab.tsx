import { useState } from 'react'
import { useRunnerStore } from '../../store/runnerStore'
import type { StageLogEntry } from '../../store/runnerStore'
import styles from './OutputTab.module.css'

export function OutputTab(): JSX.Element {
  const stageLog = useRunnerStore((s) => s.stageLog)
  const topic = useRunnerStore((s) => s.topic)
  const cost = useRunnerStore((s) => s.cost)

  if (stageLog.length === 0) {
    return (
      <div className={styles.empty}>
        No output yet — start a run to see stage results here.
      </div>
    )
  }

  return (
    <div className={styles.container}>
      <div className={styles.runHeader}>
        <span className={styles.runTopic}>{topic ?? '—'}</span>
        <span className={styles.runMeta}>${cost.toFixed(3)} · {stageLog.length} stage{stageLog.length !== 1 ? 's' : ''}</span>
      </div>
      <div className={styles.list}>
        {stageLog.map((entry, i) => (
          <OutputRow key={`${entry.stage}-${i}`} entry={entry} />
        ))}
      </div>
    </div>
  )
}

function OutputRow({ entry }: { entry: StageLogEntry }): JSX.Element {
  const [expanded, setExpanded] = useState(false)
  const [promptOpen, setPromptOpen] = useState(false)

  const durationSec = entry.durationMs != null ? (entry.durationMs / 1000).toFixed(1) + 's' : '—'
  const costStr = entry.costUsd != null ? '$' + entry.costUsd.toFixed(3) : '—'
  const exitOk = entry.exitCode === 0
  const adapterColor = entry.adapter === 'claude' ? styles.adapterClaude : entry.adapter === 'codex' ? styles.adapterCodex : entry.adapter === 'agy' ? styles.adapterAgy : ''

  return (
    <div className={styles.row}>
      <button
        type="button"
        className={styles.rowHeader}
        onClick={() => setExpanded((v) => !v)}
        {...(expanded ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
      >
        <span className={styles.chevron}>{expanded ? '▼' : '▶'}</span>
        <span className={styles.stageName}>{entry.stage}</span>
        {entry.adapter && <span className={`${styles.adapterPill} ${adapterColor}`}>{entry.adapter}</span>}
        <span className={styles.rowMeta}>{durationSec}</span>
        <span className={styles.rowMeta}>{costStr}</span>
        <span className={exitOk ? styles.exitOk : styles.exitFail}>{entry.exitCode !== null ? (exitOk ? '✓' : '✗') : '·'}</span>
      </button>

      {expanded && (
        <div className={styles.detail}>
          {entry.result != null ? (
            <div className={styles.resultBox}>{entry.result}</div>
          ) : (
            <div className={styles.resultEmpty}>No result captured</div>
          )}
          {(entry.inputTokens != null) && (
            <div className={styles.tokenRow}>
              in {entry.inputTokens?.toLocaleString()} · out {entry.outputTokens?.toLocaleString()} · cache↑ {entry.cacheCreateTokens?.toLocaleString()} · cache↓ {entry.cacheReadTokens?.toLocaleString()}
            </div>
          )}
          {entry.prompt != null && (
            <>
              <button
                type="button"
                className={styles.promptToggle}
                onClick={() => setPromptOpen((v) => !v)}
                {...(promptOpen ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
              >
                {promptOpen ? 'Hide prompt ▲' : 'Show prompt ▾'}
              </button>
              {promptOpen && (
                <div className={styles.promptBox}>{entry.prompt}</div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
