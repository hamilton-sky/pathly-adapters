import { useState } from 'react'
import { LayoutGrid, List } from 'lucide-react'
import { useRunnerStore } from '../../../store/runnerStore'
import type { StageLogEntry, HistoricalRun } from '../../../store/runnerStore'
import { StageCard } from './StageCard'
import { StageModal } from './StageModal'
import styles from './OutputTab.module.css'

type ViewMode = 'grid' | 'list'
const STORAGE_KEY = 'pathly-output-view'

function readViewMode(): ViewMode {
  try { return (localStorage.getItem(STORAGE_KEY) as ViewMode) ?? 'list' } catch { return 'list' }
}

export function OutputTab(): JSX.Element {
  const stageLog = useRunnerStore((s) => s.stageLog)
  const runHistory = useRunnerStore((s) => s.runHistory)
  const topic = useRunnerStore((s) => s.topic)
  const cost = useRunnerStore((s) => s.cost)
  const [viewMode, setViewMode] = useState<ViewMode>(readViewMode)
  const [selected, setSelected] = useState<StageLogEntry | null>(null)

  function handleViewMode(mode: ViewMode): void {
    try { localStorage.setItem(STORAGE_KEY, mode) } catch { /* noop */ }
    setViewMode(mode)
  }

  if (stageLog.length === 0 && runHistory.length === 0) {
    return <div className={styles.empty}>No output yet — start a run to see stage results here.</div>
  }

  return (
    <div className={styles.container}>
      <div className={styles.runHeader}>
        <span className={styles.runTopic}>{topic ?? '—'}</span>
        <div className={styles.headerRight}>
          <span className={styles.runMeta}>${cost.toFixed(3)} · {stageLog.length} stage{stageLog.length !== 1 ? 's' : ''}</span>
          <div className={styles.viewToggle} role="group" aria-label="Output view mode">
            <button
              type="button"
              className={viewMode === 'grid' ? `${styles.toggleBtn} ${styles.toggleBtnActive}` : styles.toggleBtn}
              onClick={() => handleViewMode('grid')}
              aria-label="Grid view"
            >
              <LayoutGrid size={15} />
            </button>
            <button
              type="button"
              className={viewMode === 'list' ? `${styles.toggleBtn} ${styles.toggleBtnActive}` : styles.toggleBtn}
              onClick={() => handleViewMode('list')}
              aria-label="List view"
            >
              <List size={15} />
            </button>
          </div>
        </div>
      </div>

      <div className={styles.scroll}>
        {runHistory.map((run, i) => (
          <HistoricalRunSection key={i} run={run} index={i + 1} viewMode={viewMode} onSelect={setSelected} />
        ))}
        <div className={viewMode === 'grid' ? styles.gridContainer : styles.listContainer}>
          {stageLog.map((entry, i) => (
            <StageCard key={`${entry.stage}-${i}`} entry={entry} viewMode={viewMode} onClick={() => setSelected(entry)} />
          ))}
        </div>
      </div>

      {selected && <StageModal entry={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}

function HistoricalRunSection({ run, index, viewMode, onSelect }: { run: HistoricalRun; index: number; viewMode: ViewMode; onSelect: (e: StageLogEntry) => void }): JSX.Element {
  const [expanded, setExpanded] = useState(false)
  const stageCount = run.stageLog.length
  const timeStr = run.runStartedAt ? new Date(run.runStartedAt).toLocaleTimeString() : '—'

  return (
    <div className={styles.historicalRun}>
      <button
        type="button"
        className={styles.historicalRunHeader}
        onClick={() => setExpanded((v) => !v)}
        {...(expanded ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
      >
        <span className={styles.chevron}>{expanded ? '-' : '+'}</span>
        <span className={styles.historicalRunLabel}>Run {index} — {stageCount} stage{stageCount !== 1 ? 's' : ''}</span>
        <span className={styles.rowMeta}>{timeStr}</span>
        <span className={styles.rowMeta}>${run.cost.toFixed(3)}</span>
      </button>
      {expanded && (
        <div className={`${styles.historicalRunBody} ${viewMode === 'grid' ? styles.gridContainer : styles.listContainer}`}>
          {run.stageLog.map((entry, i) => (
            <StageCard key={`${entry.stage}-${i}`} entry={entry} viewMode={viewMode} onClick={() => onSelect(entry)} />
          ))}
        </div>
      )}
    </div>
  )
}
