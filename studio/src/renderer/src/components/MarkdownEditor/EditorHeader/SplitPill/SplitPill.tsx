import { Wand2, SlidersHorizontal, Square, GitCompare } from 'lucide-react'
import { Tooltip } from '../../../ui'
import { ActionProgress, fmtElapsed } from '../editorProgress'
import styles from './SplitPill.module.css'

type SplitState = 'idle' | 'running' | 'success' | 'error'

interface Props {
  /** Live state of the AI Split action (drives the pill's colour/label). */
  state: SplitState
  /** Live progress while running — elapsed timer + latest output line. */
  progress?: ActionProgress | null
  /** Whether a document is open — gates every zone. */
  hasPath: boolean
  /** Idle label — the selected preset's name (e.g. "Restructure into sections"). */
  title: string
  /** A split draft is pending review — lights up the Diff segment. */
  draftReady: boolean
  /** Run the AI Split (LLM reorganizes per the selected preset → diff to review). */
  onAiSplit: () => void
  /** Stop the running engine. */
  onStop: () => void
  /** Toggle the AI-Split prompt/preset config modal. */
  onTogglePrompt: () => void
  /** Open the split draft diff viewer. */
  onReviewDraft: () => void
  /** Hide the text label when the header is in compact mode. */
  compact?: boolean
}

// One joined segmented pill: [ run (title follows preset) │ gear/stop │ Diff result ].
// The segments share borders so the whole control reads as a single unit and the
// border lifts to accent as a whole on hover. The Wand2 icon is a fixed prefix so the
// pill stays recognizable as the AI action even as its title changes with the preset.
export default function SplitPill({ state, progress, hasPath, title, draftReady, onAiSplit, onStop, onTogglePrompt, onReviewDraft, compact }: Props) {
  const label =
    state === 'running' ? (progress ? `Splitting… ${fmtElapsed(progress.elapsedS)}` : 'Splitting…')
    : state === 'success' ? 'Done' : state === 'error' ? 'Error' : title

  return (
    <div className={styles.splitPill}>
      <Tooltip
        label={state === 'running'
          ? (progress?.detail || 'Reorganizing the document…')
          : `AI restructures the document — “${title}” — and delivers a diff you review and accept`}
        placement="bottom"
      >
        <button
          type="button"
          className={styles.splitMain}
          data-state={state}
          disabled={state === 'running' || !hasPath}
          onClick={onAiSplit}
          aria-label={`AI Split — ${title}`}
        >
          <Wand2 size={13} />
          {!compact && <span className={styles.label}>{label}</span>}
        </button>
      </Tooltip>

      {state === 'running' ? (
        <Tooltip label="Stop the running engine" placement="bottom">
          <button
            type="button"
            className={styles.splitStop}
            onClick={onStop}
            aria-label="Stop split"
          >
            <Square size={11} />
          </button>
        </Tooltip>
      ) : (
        <Tooltip label="View or edit the AI Split prompt & preset" placement="bottom">
          <button
            type="button"
            className={styles.splitGear}
            data-state={state}
            disabled={!hasPath}
            onClick={onTogglePrompt}
            aria-label="Edit AI Split prompt and preset"
          >
            <SlidersHorizontal size={11} />
          </button>
        </Tooltip>
      )}

      <Tooltip
        label={draftReady
          ? 'AI Split draft ready — review the changes'
          : 'No split draft yet — run AI Split to generate one'}
        placement="bottom"
      >
        <button
          type="button"
          className={styles.splitChip}
          data-has-draft={draftReady ? 'true' : 'false'}
          disabled={!draftReady}
          onClick={onReviewDraft}
          aria-label="Review AI Split changes"
        >
          <GitCompare size={12} />
          {!compact && <span className={styles.label}>Diff</span>}
        </button>
      </Tooltip>
    </div>
  )
}
