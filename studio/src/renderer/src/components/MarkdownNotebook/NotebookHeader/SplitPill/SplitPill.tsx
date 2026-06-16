import { useState, useEffect, useRef } from 'react'
import { Wand2, Scissors, ChevronDown, SlidersHorizontal } from 'lucide-react'
import { Tooltip } from '../../../ui'
import styles from './SplitPill.module.css'

type SplitState = 'idle' | 'running' | 'success' | 'error'

interface Props {
  /** Live state of the AI Split action (drives the pill's colour/label). */
  state: SplitState
  /** Whether a document is open — gates every zone. */
  hasPath: boolean
  /** Run the AI Split (LLM reorganizes into ## sections → diff to review). */
  onAiSplit: () => void
  /** Run the deterministic "Split into cells" (parse structure, no LLM). */
  onSplitIntoCells: () => void
  /** Toggle the AI-Split prompt-peek modal. */
  onTogglePrompt: () => void
  /** Hide the text label when the header is in compact mode. */
  compact?: boolean
}

// Split-button: primary "AI Split" zone + a caret that opens a 2-mode menu
// (AI Split vs deterministic Split into cells) + the prompt gear (AI only).
// The two modes use distinct icons — Wand2 (generative) vs Scissors (structural) —
// so they stay unambiguous in compact mode where the text label is hidden.
export default function SplitPill({ state, hasPath, onAiSplit, onSplitIntoCells, onTogglePrompt, compact }: Props) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const label =
    state === 'running' ? 'Splitting…' : state === 'success' ? 'AI Split!' : state === 'error' ? 'Error' : 'AI Split'

  return (
    <div className={styles.splitPill} ref={ref}>
      <Tooltip
        label={state === 'running'
          ? 'Reorganizing the document into sections…'
          : 'AI reorganizes the document into clean ## sections — delivers a diff you review and accept'}
        placement="bottom"
      >
        <button
          type="button"
          className={styles.splitMain}
          data-state={state}
          disabled={state === 'running' || !hasPath}
          onClick={onAiSplit}
          aria-label="AI Split — reorganize document into sections"
        >
          <Wand2 size={13} />
          {!compact && <span className={styles.label}>{label}</span>}
        </button>
      </Tooltip>

      <Tooltip label="Choose split mode" placement="bottom">
        <button
          type="button"
          className={styles.splitCaret}
          data-state={state}
          disabled={!hasPath}
          aria-haspopup="menu"
          {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
          aria-label="Choose split mode"
          onClick={() => setOpen((o) => !o)}
        >
          <ChevronDown size={11} />
        </button>
      </Tooltip>

      <Tooltip label="View or edit the AI Split prompt" placement="bottom">
        <button
          type="button"
          className={styles.splitGear}
          data-state={state}
          disabled={!hasPath}
          onClick={onTogglePrompt}
          aria-label="Edit AI Split prompt"
        >
          <SlidersHorizontal size={11} />
        </button>
      </Tooltip>

      {open && (
        <div className={styles.menu} role="menu">
          <button
            type="button"
            role="menuitem"
            className={styles.item}
            onClick={() => { setOpen(false); onAiSplit() }}
          >
            <Wand2 size={13} />AI Split — reorganize into sections
          </button>
          <div className={styles.divider} />
          <button
            type="button"
            role="menuitem"
            className={styles.item}
            onClick={() => { setOpen(false); onSplitIntoCells() }}
          >
            <Scissors size={13} />Split into cells — parse structure
          </button>
        </div>
      )}
    </div>
  )
}
