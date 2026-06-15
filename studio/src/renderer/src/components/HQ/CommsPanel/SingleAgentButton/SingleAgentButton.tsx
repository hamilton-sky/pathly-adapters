import { useState, MouseEvent } from 'react'
import { createPortal } from 'react-dom'
import { Play, Settings, Square, X } from 'lucide-react'
import { useCommsStore } from '../../../../store/commsStore'
import { useStore } from '../../../../store'
import { AGENTS, SKILLS } from '../../../Monitor/ConfigurePhaseModal/configurePhaseModalData'
import { useAgentCatalog, useSkillCatalog } from '../../../Monitor/ConfigurePhaseModal/hooks/usePhaseModalCatalog'
import s from './SingleAgentButton.module.css'

interface Props {
  /** Board key: feature id, 'project', or 'global'. */
  boardKey: string
}

type RunState = 'idle' | 'running' | 'busy' | 'done'

const RUN_HINT: Record<RunState, string> = {
  idle: 'Start',
  running: 'Running…',
  busy: 'Board busy',
  done: 'Done',
}

const EMPTY_WARN = 'Add instructions, or pick an agent or skill'

/**
 * C2 — single-agent control: a connected Start ▸ ⚙ segmented button above the
 * board input. Start spawns one agent on this board (POST /comms/run). Agent and
 * skill are both optional ("— none —"); Start with nothing set warns the user.
 */
export function SingleAgentButton({ boardKey }: Props): JSX.Element {
  const [open, setOpen] = useState(false)
  const [agent, setAgent] = useState<string>('')   // '' = none
  const [skill, setSkill] = useState<string>('')   // '' = none
  const [instructions, setInstructions] = useState('')
  const [interactive, setInteractive] = useState(false)
  const [warn, setWarn] = useState<string | null>(null)

  const runSingleAgent = useCommsStore((st) => st.runSingleAgent)
  const stopBoard = useCommsStore((st) => st.stopBoard)
  const boardRunState = useCommsStore((st) => st.boardRunState)
  const runState: RunState = (boardRunState[boardKey] as RunState | undefined) ?? 'idle'
  const running = runState === 'running'
  const active = runState === 'running' || runState === 'busy'

  // Full agent/skill lists from the real core/ dirs (falls back to the common
  // quick-pick lists until the catalog has loaded).
  const projectPath = useStore((st) => st.projectPath)
  const agentCatalog = useAgentCatalog(projectPath)
  const skillCatalog = useSkillCatalog(projectPath)
  const agentOptions = agentCatalog.length ? agentCatalog.map((i) => i.name) : [...AGENTS]
  const skillOptions = skillCatalog.length ? skillCatalog.map((i) => i.name) : [...SKILLS]

  /** Returns true if the run was started, false if blocked (running or empty). */
  function start(): boolean {
    if (running) return false
    if (!instructions.trim() && !agent && !skill) {
      setWarn(EMPTY_WARN)
      window.setTimeout(() => setWarn(null), 3500)
      return false
    }
    setWarn(null)
    runSingleAgent(boardKey, instructions, agent || undefined, skill || undefined, interactive)
    return true
  }

  function backdrop(e: MouseEvent<HTMLDivElement>): void {
    if (e.target === e.currentTarget) setOpen(false)
  }

  return (
    <div className={s.row}>
      <div className={s.group}>
        <button
          type="button"
          className={s.startBtn}
          data-state={runState !== 'idle' ? runState : undefined}
          title="Run one agent on this board"
          aria-label="Run one agent on this board"
          disabled={running}
          onClick={() => { start() }}
        >
          <Play size={10} />
          <span className={s.startLabel}>{RUN_HINT[runState]}</span>
        </button>
        <button
          type="button"
          className={s.gearBtn}
          title="Configure the agent prompt"
          aria-label="Configure the agent prompt"
          {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
          onClick={() => setOpen(true)}
        >
          <Settings size={11} />
        </button>
        <button
          type="button"
          className={s.stopBtn}
          title="Stop the running agent"
          aria-label="Stop the running agent"
          disabled={!active}
          onClick={() => stopBoard(boardKey)}
        >
          <Square size={9} />
        </button>
      </div>
      {warn && <span className={s.warn} role="alert">{warn}</span>}

      {open && createPortal(
        <div className={s.backdrop} onClick={backdrop}>
          <div className={s.modal} role="dialog" aria-modal="true" aria-label="Configure single agent">
            <header className={s.header}>
              <Settings size={15} />
              <span className={s.title}>Single agent — prompt</span>
              <span className={s.spacer} />
              <button type="button" className={s.closeBtn} onClick={() => setOpen(false)} aria-label="Close">
                <X size={14} />
              </button>
            </header>

            <div className={s.body}>
              <label className={s.label} htmlFor="sa-agent">Agent (optional)</label>
              <select
                id="sa-agent"
                className={s.select}
                value={agent}
                onChange={(e) => setAgent(e.currentTarget.value)}
              >
                <option value="">— none —</option>
                {agentOptions.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>

              <label className={s.label} htmlFor="sa-skill">Skill (optional)</label>
              <select
                id="sa-skill"
                className={s.select}
                value={skill}
                onChange={(e) => setSkill(e.currentTarget.value)}
              >
                <option value="">— none —</option>
                {skillOptions.map((sk) => <option key={sk} value={sk}>{sk}</option>)}
              </select>

              <span className={s.label}>Mode</span>
              <div className={s.modeRow} role="radiogroup" aria-label="Run mode">
                <button
                  type="button"
                  className={s.modeBtn}
                  {...(!interactive ? { 'data-on': '' } : {})}
                  {...(!interactive ? { 'aria-checked': 'true' } : { 'aria-checked': 'false' })}
                  role="radio"
                  onClick={() => setInteractive(false)}
                >
                  Headless
                </button>
                <button
                  type="button"
                  className={s.modeBtn}
                  {...(interactive ? { 'data-on': '' } : {})}
                  {...(interactive ? { 'aria-checked': 'true' } : { 'aria-checked': 'false' })}
                  role="radio"
                  onClick={() => setInteractive(true)}
                >
                  Interactive
                </button>
              </div>
              <p className={s.modeHint}>
                {interactive
                  ? 'Opens a live session and types the prompt for you — stays open for follow-ups.'
                  : 'One-shot: runs the prompt and exits when done.'}
              </p>

              <label className={s.label} htmlFor="sa-instr">System prompt / instructions</label>
              <textarea
                id="sa-instr"
                className={s.textarea}
                value={instructions}
                onChange={(e) => setInstructions(e.currentTarget.value)}
                placeholder="What should this agent do with the board's context?"
              />
              {warn && <span className={s.warn} role="alert">{warn}</span>}
            </div>

            <footer className={s.footer}>
              <span className={s.spacer} />
              <button type="button" className={s.btnQuiet} onClick={() => setOpen(false)}>Done</button>
              <button
                type="button"
                className={s.btnRun}
                onClick={() => { if (start()) setOpen(false) }}
                disabled={running}
              >
                <Play size={12} /> Start
              </button>
            </footer>
          </div>
        </div>,
        document.body,
      )}
    </div>
  )
}
