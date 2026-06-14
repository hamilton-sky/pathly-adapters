import { useState } from 'react'
import { Settings, BookOpen, Check, X } from 'lucide-react'
import { Modal } from './components/Modal/Modal'
import { StatePill } from './components/StatePill/StatePill'
import { AssemblyRecipe } from './components/AssemblyRecipe/AssemblyRecipe'
import { ChipGroup } from './components/ChipGroup/ChipGroup'
import { SectionLabel } from './components/SectionLabel/SectionLabel'
import { PromptPreview } from './components/PromptPreview/PromptPreview'
import { Button } from './components/Button/Button'
import { CLI_HOSTS, AGENTS, SKILLS, STAGE_DEFAULTS, SKILL_PROMPTS } from './configurePhaseModalData'
import type { StageName, PhaseConfig } from './types'
import styles from './ConfigurePhaseModal.module.css'

interface ConfigurePhaseModalProps {
  stage: StageName
  onClose: () => void
  /** Seed the selection (otherwise falls back to the stage defaults). */
  initial?: Partial<PhaseConfig>
  /** Override the catalogs (defaults come from the local data module). */
  hosts?: string[]
  agents?: string[]
  skills?: string[]
  /** Live markdown for the selected skill / agent prompts. */
  skillPrompt?: string
  agentPrompt?: string
  /** Callbacks — all optional so the component works standalone. */
  onApply?: (config: PhaseConfig) => void
  onReset?: () => void
  onOpenNotebook?: (skill: string) => void
  onAddAgent?: () => void
  onAddSkill?: () => void
}

/**
 * Configure-phase modal — composes the small presentational components into
 * the full dialog. State for host / agent / skill is held locally; everything
 * else is surfaced through props so the component is reusable and testable.
 */
export function ConfigurePhaseModal({
  stage,
  onClose,
  initial,
  hosts = [...CLI_HOSTS],
  agents = [...AGENTS],
  skills = [...SKILLS],
  skillPrompt,
  agentPrompt,
  onApply,
  onReset,
  onOpenNotebook,
  onAddAgent,
  onAddSkill,
}: ConfigurePhaseModalProps): JSX.Element {
  const defaults = STAGE_DEFAULTS[stage] ?? { agent: 'builder', skill: 'fix/build' }
  const [host, setHost] = useState(initial?.host ?? 'Claude Code')
  const [agent, setAgent] = useState(initial?.agent ?? defaults.agent)
  const [skill, setSkill] = useState(initial?.skill ?? defaults.skill)
  const [saved, setSaved] = useState(false)

  const preview = skillPrompt ?? SKILL_PROMPTS[skill] ?? `# ${skill}\n\nNo preview available.`
  const isModified = host !== 'Claude Code' || agent !== defaults.agent || skill !== defaults.skill

  function handleApply(): void {
    onApply?.({ host, agent, skill })
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  function handleReset(): void {
    setHost('Claude Code')
    setAgent(defaults.agent)
    setSkill(defaults.skill)
    onReset?.()
  }

  return (
    <Modal onClose={onClose} ariaLabel={`Configure ${stage} phase`}>
      <header className={styles.header}>
        <span className={styles.gear}>
          <Settings size={16} />
        </span>
        <span className={styles.title}>Configure phase</span>
        <span className={styles.spacer} />
        <StatePill state={stage} />
        <button type="button" className={styles.close} onClick={onClose} aria-label="Close">
          <X size={16} />
        </button>
      </header>

      <div className={styles.body}>
        <AssemblyRecipe host={host} agent={agent} skill={skill} />

        <ChipGroup
          label="CLI Host"
          variant="host"
          options={hosts}
          value={host}
          onSelect={setHost}
        />
        <ChipGroup
          label="Agent"
          variant="agent"
          mono
          options={agents}
          value={agent}
          onSelect={setAgent}
          onAdd={onAddAgent}
        />
        <ChipGroup
          label="Skill"
          variant="skill"
          mono
          options={skills}
          value={skill}
          onSelect={setSkill}
          onAdd={onAddSkill}
        />

        <div>
          <SectionLabel>Prompt Preview</SectionLabel>
          <PromptPreview
            label={`${skill} · ${agent} · ${host}`}
            skillPrompt={preview}
            agentPrompt={agentPrompt}
            isModified={isModified}
          />
        </div>
      </div>

      <footer className={styles.footer}>
        <Button variant="ghost" icon={<BookOpen size={14} />} onClick={() => onOpenNotebook?.(skill)}>
          Open skill in Notebook
        </Button>
        <span className={styles.spacer} />
        <Button variant="quiet" onClick={handleReset}>
          Reset to default
        </Button>
        <Button variant="quiet" onClick={onClose}>
          Cancel
        </Button>
        <Button variant="primary" icon={<Check size={14} />} onClick={handleApply}>
          {saved ? 'Saved' : 'Apply'}
        </Button>
      </footer>
    </Modal>
  )
}
