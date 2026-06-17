import { useState } from 'react'
import { Send } from 'lucide-react'
import { useStore } from '../../../../store'
import { AGENTS, SKILLS } from '../../../Monitor/ConfigurePhaseModal/configurePhaseModalData'
import { useAgentCatalog, useSkillCatalog } from '../../../Monitor/ConfigurePhaseModal/hooks/usePhaseModalCatalog'
import { ENGINES, PROGRESS_LEVELS, SYSTEM_PROMPTS } from './agentFormData'
import s from './SingleAgentButton.module.css'

export interface SingleAgentConfig {
  agent?: string
  skill?: string
  systemPrompt?: string
  interactive?: boolean
  /** Which CLI to spawn. */
  adapter?: string
  /** How often a headless agent posts progress to the board. */
  progress?: string
  /** The prompt typed in the form — posted to the board and sent to the agent. */
  message?: string
}

interface Props {
  running: boolean
  onRun: (cfg: SingleAgentConfig) => void
  onClose: () => void
}

// One-agent mode of the run modal: configuration (engine · agent · skill · system
// prompt · mode) + a message box. "Send to agent" posts the message to the board
// AND runs the configured agent on it.
export function AgentForm({ running, onRun, onClose }: Props): JSX.Element {
  const [engine, setEngine] = useState<string>('claude')
  const [agent, setAgent] = useState<string>('')
  const [skill, setSkill] = useState<string>('')
  const [sysName, setSysName] = useState<string>('')   // '' = none
  const [interactive, setInteractive] = useState(false)
  const [progress, setProgress] = useState<string>('normal')
  const [message, setMessage] = useState<string>('')

  // Full agent/skill lists from the real core/ dirs (fall back to common picks).
  const projectPath = useStore((st) => st.projectPath)
  const agentCatalog = useAgentCatalog(projectPath)
  const skillCatalog = useSkillCatalog(projectPath)
  const agentOptions = agentCatalog.length ? agentCatalog.map((i) => i.name) : [...AGENTS]
  const skillOptions = skillCatalog.length ? skillCatalog.map((i) => i.name) : [...SKILLS]

  // A run needs something to act on: a typed message, a skill (which encodes the
  // task), or a system prompt (a directive). Any one of the three enables Send.
  const canSend = !running && (message.trim().length > 0 || skill !== '' || sysName !== '')

  function send(): void {
    if (!canSend) return
    const sys = SYSTEM_PROMPTS.find((p) => p.name === sysName)?.prompt
    onRun({
      adapter: engine,
      agent: agent || undefined,
      skill: skill || undefined,
      systemPrompt: sys,
      interactive,
      // Progress cadence only applies headless — interactive shows the terminal.
      progress: interactive ? undefined : progress,
      message: message.trim(),
    })
    setMessage('')
    onClose()
  }

  return (
    <>
      <div className={s.body}>
        <label className={s.label} htmlFor="sa-message">Message <span className={s.optional}>· optional if you pick a skill or system prompt</span></label>
        <textarea
          id="sa-message"
          className={s.textarea}
          placeholder="What should the agent do? Posted to the board and sent to the agent. Optional if a skill or system prompt is set."
          value={message}
          onChange={(e) => setMessage(e.currentTarget.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); send() }
          }}
        />

        <label className={s.label} htmlFor="sa-engine">Engine</label>
        <select id="sa-engine" className={s.select} value={engine} onChange={(e) => setEngine(e.currentTarget.value)}>
          {ENGINES.map((en) => <option key={en.value} value={en.value}>{en.label}</option>)}
        </select>

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

        {!interactive && (
          <>
            <label className={s.label} htmlFor="sa-progress">Board updates <span className={s.optional}>· how often the agent posts progress</span></label>
            <select id="sa-progress" className={s.select} value={progress} onChange={(e) => setProgress(e.currentTarget.value)}>
              {PROGRESS_LEVELS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
          </>
        )}
        <p className={s.modeHint}>
          Sending posts your message to the board and runs the agent on it. The board’s own input box just adds a note — it doesn’t call an agent.
        </p>
      </div>

      <footer className={s.footer}>
        <span className={s.spacer} />
        <button type="button" className={s.btnQuiet} onClick={onClose}>Cancel</button>
        <button
          type="button"
          className={s.btnRun}
          onClick={send}
          disabled={!canSend}
          title={running
            ? 'An agent is already running on this board'
            : (!canSend ? 'Add a message, or pick a skill or system prompt' : undefined)}
        >
          <Send size={12} /> Send to agent
        </button>
      </footer>
    </>
  )
}
