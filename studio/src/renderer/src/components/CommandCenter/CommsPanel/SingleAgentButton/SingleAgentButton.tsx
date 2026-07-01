import { useState, MouseEvent } from 'react'
import { createPortal } from 'react-dom'
import { Settings, X, Bot, GitBranch } from 'lucide-react'
import { useCommsStore } from '../../../../store/commsStore'
import { useElapsedProgress } from '../../../shared/RunPill/progress'
import { RunPill } from '../../../shared/RunPill/RunPill'
import { AgentForm, type SingleAgentConfig } from './AgentForm'
import { FlowForm } from './FlowForm'
import s from './SingleAgentButton.module.css'

export type { SingleAgentConfig }

interface Props {
  /** Board key: feature id, 'project', or 'global'. */
  boardKey: string
  /** Post the modal message to the board, then run the configured agent on it. */
  onRun: (cfg: SingleAgentConfig) => void
  /** Launch a board-scoped flow (debug, quick-fix, explore, test, team) on this board. */
  onRunFlow: (flow: string, opts: { interactive: boolean }) => void
}

type RunState = 'idle' | 'running' | 'busy' | 'done'
type Mode = 'agent' | 'flow'

/**
 * Run control on the board's Reads row: [⚙ Run │ ⏹ Stop].
 *
 * The ⚙ button opens a dialog with two modes:
 *  - Single agent — configure + send one prompt to one agent (board-scoped /comms/run).
 *  - Flow — pick a board-scoped flow, preview it, and run the whole pipeline (/runner/start).
 *
 * Neither depends on a goal or task DAG — goal planning is the board's Evaluate control
 * (target a goal), and goal execution is the goal card's Run.
 */
export function SingleAgentButton({ boardKey, onRun, onRunFlow }: Props): JSX.Element {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<Mode>('agent')

  const stopBoard = useCommsStore((st) => st.stopBoard)
  const boardRunState = useCommsStore((st) => st.boardRunState)
  const boardRunStart = useCommsStore((st) => st.boardRunStart)
  const runState: RunState = (boardRunState[boardKey] as RunState | undefined) ?? 'idle'
  const running = runState === 'running'
  const progress = useElapsedProgress(boardRunStart[boardKey] || undefined)

  function backdrop(e: MouseEvent<HTMLDivElement>): void {
    if (e.target === e.currentTarget) setOpen(false)
  }
  const close = (): void => setOpen(false)

  return (
    <div className={s.row}>
      {/* The main button opens the run dialog (it doesn't run directly); the shared
          RunPill gives it the same timer + stop as every other board spawn control. */}
      <RunPill
        idleLabel="Run"
        icon={<Settings size={10} />}
        state={runState}
        progress={progress}
        onRun={() => setOpen(true)}
        onStop={() => stopBoard(boardKey)}
      />

      {open && createPortal(
        <div className={s.backdrop} onClick={backdrop}>
          <div className={s.modal} role="dialog" aria-modal="true" aria-label="Run on this board">
            <header className={s.header}>
              <Settings size={15} className={s.headerIcon} />
              <span className={s.title}>Run on this board</span>
              <span className={s.spacer} />
              <button type="button" className={s.closeBtn} onClick={close} aria-label="Close">
                <X size={14} />
              </button>
            </header>

            <div className={s.tabRow} role="tablist" aria-label="Run mode">
              <button
                type="button"
                className={s.tab}
                role="tab"
                {...(mode === 'agent' ? { 'data-on': '', 'aria-selected': 'true' } : { 'aria-selected': 'false' })}
                onClick={() => setMode('agent')}
              >
                <Bot size={13} /> Single agent
              </button>
              <button
                type="button"
                className={s.tab}
                role="tab"
                {...(mode === 'flow' ? { 'data-on': '', 'aria-selected': 'true' } : { 'aria-selected': 'false' })}
                onClick={() => setMode('flow')}
              >
                <GitBranch size={13} /> Flow
              </button>
            </div>

            {mode === 'agent'
              ? <AgentForm running={running} onRun={onRun} onClose={close} />
              : <FlowForm running={running} onRunFlow={onRunFlow} onClose={close} />}
          </div>
        </div>,
        document.body,
      )}
    </div>
  )
}
