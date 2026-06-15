import { useState, MouseEvent } from 'react'
import { createPortal } from 'react-dom'
import { Play, Settings, Square, X } from 'lucide-react'
import { useCommsStore } from '../../../../store/commsStore'
import { useStore } from '../../../../store'
import { AGENTS, SKILLS } from '../../../Monitor/ConfigurePhaseModal/configurePhaseModalData'
import { useAgentCatalog, useSkillCatalog } from '../../../Monitor/ConfigurePhaseModal/hooks/usePhaseModalCatalog'
import s from './SingleAgentButton.module.css'

export interface SingleAgentConfig {
  agent?: string
  skill?: string
  systemPrompt?: string
  interactive?: boolean
}

interface Props {
  /** Board key: feature id, 'project', or 'global'. */
  boardKey: string
  /** Post the board input (if any) then run the agent on it. Owned by the panel. */
  onRun: (cfg: SingleAgentConfig) => void
}

type RunState = 'idle' | 'running' | 'busy' | 'done'

const RUN_HINT: Record<RunState, string> = {
  idle: 'Start',
  running: 'Running…',
  busy: 'Board busy',
  done: 'Done',
}

// Fixed starter system-prompt presets (user-editable presets are a follow-up).
const SYSTEM_PROMPTS: { name: string; prompt: string }[] = [
  { name: 'Summarizer', prompt: 'Summarize the request concisely. Be terse and factual.' },
  { name: 'Code reviewer', prompt: 'Review the referenced code for bugs, security issues, and edge cases. Report findings only — do not edit files.' },
  { name: 'Researcher', prompt: 'Research the topic, cite sources, and report what you found and what is uncertain.' },
  { name: 'Explainer', prompt: 'Explain clearly and simply, with a short concrete example.' },
  { name: 'Planner', prompt: 'Break the request into a short ordered list of concrete steps.' },
]

/**
 * C2 — single-agent control: a connected [▶ Start │ ⚙ │ ⏹ Stop] on the board's
 * Reads row. The ⚙ modal is config only (Agent · Skill · System prompt · Mode);
 * the TASK is whatever the human types in the board message box — Start posts it
 * (via the panel's onRun) then runs the agent on it.
 */
export function SingleAgentButton({ boardKey, onRun }: Props): JSX.Element {
  const [open, setOpen] = useState(false)
  const [agent, setAgent] = useState<string>('')
  const [skill, setSkill] = useState<string>('')
  const [sysName, setSysName] = useState<string>('')   // '' = none
  const [interactive, setInteractive] = useState(false)

  const stopBoard = useCommsStore((st) => st.stopBoard)
  const boardRunState = useCommsStore((st) => st.boardRunState)
  const runState: RunState = (boardRunState[boardKey] as RunState | undefined) ?? 'idle'
  const running = runState === 'running'
  const active = runState === 'running' || runState === 'busy'

  // Full agent/skill lists from the real core/ dirs (fall back to common picks).
  const projectPath = useStore((st) => st.projectPath)
  const agentCatalog = useAgentCatalog(projectPath)
  const skillCatalog = useSkillCatalog(projectPath)
  const agentOptions = agentCatalog.length ? agentCatalog.map((i) => i.name) : [...AGENTS]
  const skillOptions = skillCatalog.length ? skillCatalog.map((i) => i.name) : [...SKILLS]

  function start(): void {
    if (running) return
    const sys = SYSTEM_PROMPTS.find((p) => p.name === sysName)?.prompt
    onRun({ agent: agent || undefined, skill: skill || undefined, systemPrompt: sys, interactive })
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
          title="Post the board input and run one agent on it"
          aria-label="Run one agent on this board"
          disabled={running}
          onClick={start}
        >
          <Play size={10} />
          <span className={s.startLabel}>{RUN_HINT[runState]}</span>
        </button>
        <button
          type="button"
          className={s.gearBtn}
          title="Configure the agent (agent · skill · system prompt · mode)"
          aria-label="Configure the agent"
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

      {open && createPortal(
        <div className={s.backdrop} onClick={backdrop}>
          <div className={s.modal} role="dialog" aria-modal="true" aria-label="Configure single agent">
            <header className={s.header}>
              <Settings size={15} />
              <span className={s.title}>Single agent</span>
              <span className={s.spacer} />
              <button type="button" className={s.closeBtn} onClick={() => setOpen(false)} aria-label="Close">
                <X size={14} />
              </button>
            </header>

            <div className={s.body}>
              <label className={s.label} htmlFor="sa-agent">Agent</label>
              <select id="sa-agent" className={s.select} value={agent} onChange={(e) => setAgent(e.currentTarget.value)}>
                <option value="">— none —</option>
                {agentOptions.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>

              <label className={s.label} htmlFor="sa-skill">Skill</label>
              <select id="sa-skill" className={s.select} value={skill} onChange={(e) => setSkill(e.currentTarget.value)}>
                <option value="">— none —</option>
                {skillOptions.map((sk) => <option key={sk} value={sk}>{sk}</option>)}
              </select>

              <label className={s.label} htmlFor="sa-sys">System prompt</label>
              <select id="sa-sys" className={s.select} value={sysName} onChange={(e) => setSysName(e.currentTarget.value)}>
                <option value="">— none —</option>
                {SYSTEM_PROMPTS.map((p) => <option key={p.name} value={p.name}>{p.name}</option>)}
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
              <p className={s.modeHint}>
                The task is what you type in the board message box. Start posts it, then runs the agent on it.
              </p>
            </div>

            <footer className={s.footer}>
              <span className={s.spacer} />
              <button type="button" className={s.btnQuiet} onClick={() => setOpen(false)}>Done</button>
              <button
                type="button"
                className={s.btnRun}
                onClick={() => { setOpen(false); start() }}
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
