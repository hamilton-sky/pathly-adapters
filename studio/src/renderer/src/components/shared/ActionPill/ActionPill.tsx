import type { ReactNode, Ref } from 'react'
import { SlidersHorizontal, Square } from 'lucide-react'
import { Tooltip } from '../../ui'
import { ActionProgress, fmtElapsed } from '../RunPill/progress'
import type { PillState } from '../RunPill/RunPill'
import styles from './ActionPill.module.css'

interface Props {
  /** Live state — drives colour and label (shares RunPill's vocabulary). */
  state: PillState
  /** Live progress while running — elapsed timer + latest output line. */
  progress?: ActionProgress | null
  /** Gates the run + gear (a doc is open / the action is available). */
  hasPath: boolean
  /** Idle label on the main button (the selected preset/lens name). */
  title: string
  /** Verb shown while running, e.g. "Splitting", "Analyzing", "Evaluating". */
  runningVerb: string
  /** Leading icon on the main button (Wand2 / ScanText / Sparkles). */
  mainIcon: ReactNode
  /** Main-button tooltip when idle. */
  idleTip: string
  /** Main-button tooltip while running, used until the engine emits a live output line. */
  runningTip: string
  /** aria-label stem, e.g. "AI Split", "Evaluate". */
  ariaName: string
  /** Run the action. */
  onRun: () => void
  /** Stop the running engine. */
  onStop: () => void
  /** Gear segment tooltip + aria-label. */
  configTip: string
  /** Toggle the prompt/preset config (modal or popover — owned by the consumer). */
  onToggleConfig: () => void
  /** Forwarded to the gear button so a consumer can anchor a config popover to it. */
  gearRef?: Ref<HTMLButtonElement>
  /** Result segment (optional — omit for a run+gear-only pill like Evaluate). */
  resultIcon?: ReactNode
  resultLabel?: string
  resultReady?: boolean
  resultTip?: string
  onOpenResult?: () => void
  /** Result-chip glow colour (only meaningful when a result segment is present). */
  tone?: 'green' | 'amber'
  /** Hide text labels (compact toolbar). */
  compact?: boolean
}

// One joined segmented pill: [ run (title follows preset) │ gear↔stop │ result chip? ].
// Shared by the editor's AI Split/Analyze (which carry a Diff/Report result chip) and the
// board's Evaluate (run + config gear, no chip). The result segment is optional; the gear
// can forward a ref so a consumer can anchor a config popover to it.
export default function ActionPill({
  state, progress, hasPath, title, runningVerb, mainIcon, idleTip, runningTip, ariaName,
  onRun, onStop, configTip, onToggleConfig, gearRef,
  resultIcon, resultLabel, resultReady, resultTip, onOpenResult, tone, compact,
}: Props) {
  const hasResult = resultLabel !== undefined
  const label =
    state === 'running' ? (progress ? `${runningVerb}… ${fmtElapsed(progress.elapsedS)}` : `${runningVerb}…`)
    : state === 'busy' ? 'Busy'
    : state === 'done' ? 'Done'
    : state === 'error' ? 'Error'
    : title

  return (
    <div className={styles.pill} data-tone={tone} {...(hasResult ? { 'data-has-chip': 'true' } : {})}>
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
            ref={gearRef}
            type="button"
            className={styles.gear}
            data-state={state}
            disabled={!hasPath}
            onClick={onToggleConfig}
            aria-label={configTip}
          >
            <SlidersHorizontal size={11} />
          </button>
        </Tooltip>
      )}

      {hasResult && (
        <Tooltip label={resultTip ?? ''} placement="bottom">
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
      )}
    </div>
  )
}
