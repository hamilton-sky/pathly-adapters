import type { ReactNode } from 'react'
import { SlidersHorizontal, Square } from 'lucide-react'
import { Tooltip } from '../../../ui'
import { ActionProgress, fmtElapsed } from '../editorProgress'
import styles from './ActionPill.module.css'

export type ActionPillState = 'idle' | 'running' | 'success' | 'error'

interface Props {
  /** Live state — drives colour and label. */
  state: ActionPillState
  /** Live progress while running — elapsed timer + latest output line. */
  progress?: ActionProgress | null
  /** A document is open — gates every zone. */
  hasPath: boolean
  /** Idle label on the main button (the selected preset/lens name). */
  title: string
  /** Verb shown while running, e.g. "Splitting", "Analyzing". */
  runningVerb: string
  /** Leading icon on the main button (Wand2 / ScanText). */
  mainIcon: ReactNode
  /** Main-button tooltip when idle. */
  idleTip: string
  /** Main-button tooltip while running, used until the engine emits a live output line. */
  runningTip: string
  /** aria-label stem, e.g. "AI Split". */
  ariaName: string
  /** Run the action (opens the confirm-preview). */
  onRun: () => void
  /** Stop the running engine. */
  onStop: () => void
  /** Gear segment tooltip. */
  configTip: string
  /** Toggle the prompt/preset config modal. */
  onToggleConfig: () => void
  /** Result segment (rightmost) icon (GitCompare / FileSearch). */
  resultIcon: ReactNode
  /** Result segment label ("Diff" / "Report"). */
  resultLabel: string
  /** A result (draft/report) exists — lights up the chip. */
  resultReady: boolean
  /** Result segment tooltip (caller computes the multi-state text). */
  resultTip: string
  /** Open or toggle the result; only wired when a result exists. */
  onOpenResult?: () => void
  /** Result-chip glow colour: Split delivers a green Diff, Analyze an amber Report. */
  tone: 'green' | 'amber'
  /** Hide text labels (compact toolbar). */
  compact?: boolean
}

// One joined segmented pill: [ run (title follows preset) │ gear↔stop │ result chip ].
// Shared by AI Split and AI Analyze — they differ only in icons, labels, and the result
// tone. Segments share borders so the control reads as a single unit; the Wand2/ScanText
// icon is a fixed prefix so the pill stays recognizable even as its title changes.
export default function ActionPill({
  state, progress, hasPath, title, runningVerb, mainIcon, idleTip, runningTip, ariaName,
  onRun, onStop, configTip, onToggleConfig, resultIcon, resultLabel, resultReady, resultTip, onOpenResult, tone, compact,
}: Props) {
  const label =
    state === 'running' ? (progress ? `${runningVerb}… ${fmtElapsed(progress.elapsedS)}` : `${runningVerb}…`)
    : state === 'success' ? 'Done'
    : state === 'error' ? 'Error'
    : title

  return (
    <div className={styles.pill} data-tone={tone}>
      <Tooltip label={state === 'running' ? (progress?.detail || runningTip) : idleTip} placement="bottom">
        <button
          type="button"
          className={styles.main}
          data-state={state}
          disabled={state === 'running' || !hasPath}
          onClick={onRun}
          aria-label={`${ariaName} — ${title}`}
        >
          {mainIcon}
          {!compact && <span className={styles.label}>{label}</span>}
        </button>
      </Tooltip>

      {state === 'running' ? (
        <Tooltip label="Stop the running engine" placement="bottom">
          <button type="button" className={styles.stop} onClick={onStop} aria-label={`Stop ${ariaName}`}>
            <Square size={11} />
          </button>
        </Tooltip>
      ) : (
        <Tooltip label={configTip} placement="bottom">
          <button
            type="button"
            className={styles.gear}
            data-state={state}
            disabled={!hasPath}
            onClick={onToggleConfig}
            aria-label={`Edit ${ariaName} prompt`}
          >
            <SlidersHorizontal size={11} />
          </button>
        </Tooltip>
      )}

      <Tooltip label={resultTip} placement="bottom">
        <button
          type="button"
          className={styles.chip}
          data-has-result={resultReady ? 'true' : 'false'}
          disabled={!resultReady}
          onClick={resultReady ? onOpenResult : undefined}
          aria-label={resultLabel}
        >
          {resultIcon}
          {!compact && <span className={styles.label}>{resultLabel}</span>}
        </button>
      </Tooltip>
    </div>
  )
}
