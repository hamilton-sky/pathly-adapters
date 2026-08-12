import { useState, MouseEvent } from 'react'
import { createPortal } from 'react-dom'
import { Settings, X, Bot, GitBranch, Sparkles } from 'lucide-react'
import { useCommsStore } from '../../../../store/commsStore'
import { useElapsedProgress } from '../../../shared/RunPill/progress'
import { RunPill } from '../../../shared/RunPill/RunPill'
import { AgentForm, type SingleAgentConfig } from './AgentForm'
import { FlowForm } from './FlowForm'
import { FlowGatePreview } from '../../../shared/FlowGatePreview/FlowGatePreview'
import s from './SingleAgentButton.module.css'



interface Props {
  /** Board key: feature id, 'project', or 'global'. */
  boardKey: string
  /** Post the modal message to the board, then run the configured agent on it. */
  onRun: (cfg: SingleAgentConfig) => void
  /** Launch a board-scoped flow (debug, quick-fix, explore, test, team) on this board.
   *  `stageOverrides` carries the flow gate's transient per-stage prompt trims, keyed by
   *  FSM state — see FlowGatePreview. */
  onRunFlow: (flow: string, opts: { interactive: boolean; stageOverrides?: Record<string, string> }) => void
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
  // The flow gate preview is owned HERE (not inside FlowForm) so opening it can CLOSE the run
  // dialog — the gate then shows as the sole modal INSTEAD of stacking under this dialog (which
  // sits at a high z-index). Confirming the gate is what actually starts the flow.
  const [gate, setGate] = useState<{ flow: string; interactive: boolean } | null>(null)

  const stopBoard = useCommsStore((st) => st.stopBoard)
  const boardRunState = useCommsStore((st) => st.boardRunState)
  const boardRunStart = useCommsStore((st) => st.boardRunStart)
  const runState: RunState = (boardRunState[boardKey] as RunState | undefined) ?? 'idle'
  const running = runState === 'running'
  const progress = useElapsedProgress(boardRunStart[boardKey] || undefined)
  // Flow tab is offered on feature AND project boards (global has no board flow). Feature
  // flows go through /runner/start; the project board's project-consultation can't (that route
  // rejects the reserved 'project' scope), so the caller's onRunFlow routes it to the
  // project-decompose endpoint instead. FlowForm scopes its list per board.
  const canFlow = boardKey !== 'global'

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
        icon={<Sparkles size={10} />}
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

            {canFlow && (
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
            )}

            {canFlow && mode === 'flow'
              ? <FlowForm boardKey={boardKey} running={running} onOpenGate={(flow, interactive) => { setOpen(false); setGate({ flow, interactive }) }} onClose={close} />
              : <AgentForm running={running} onRun={onRun} onClose={close} />}
          </div>
        </div>,
        document.body,
      )}

      {gate && (
        <FlowGatePreview
          flow={gate.flow}
          boardKey={boardKey}
          interactive={gate.interactive}
          onConfirm={(stageOverrides) => {
            onRunFlow(gate.flow, { interactive: gate.interactive, stageOverrides })
            setGate(null)
          }}
          onCancel={() => setGate(null)}
        />
      )}
    </div>
  )
}
