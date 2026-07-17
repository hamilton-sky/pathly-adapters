import { useState, useMemo, useEffect } from 'react'
import { Send } from 'lucide-react'
import { useStore } from '../../../../store'
import { useUiStore } from '../../../../store/uiStore'
import {
  AGENTS, SKILLS, SKILL_PROMPTS, SKILL_FILE_PATHS, AGENT_FILE_PATHS,
} from '../../../Monitor/ConfigurePhaseModal/configurePhaseModalData'
import { useAgentCatalog, useSkillCatalog } from '../../../Monitor/ConfigurePhaseModal/hooks/usePhaseModalCatalog'
import { BoardSelect, type BoardSelectOption } from '../../../shared/BoardSelect/BoardSelect'
import { PromptBanner, usePromptContent, findPath } from '../../../shared/PromptPreview/PromptPreview'
import { useMergedPresets } from '../../../shared/PromptActionConfig/useMergedPresets'
import { PresetAddRow } from '../../../shared/PromptActionConfig/PresetAddRow'
import { ENGINES, PROGRESS_LEVELS, SYSTEM_PROMPTS } from './agentFormData'
import SendPreviewModal from '../../../shared/SendPreviewModal/SendPreviewModal'
import { AbilityToggles } from '../../../shared/AbilityToggles/AbilityToggles'
import type { Ability } from '../../../../services/abilities'
import { composeSkillPrompt, headingLayers, type ComposedSegment } from '../../../../services/skillCompose'
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
  /** Layer-3 ability library row ids to compose after the skill's fragments. */
  abilityIds?: string[]
  /** Gate "use once" prompt override (Sections trim) — the composed body, sent verbatim. */
  promptOverride?: string
}

interface Props {
  running: boolean
  onRun: (cfg: SingleAgentConfig) => void
  onClose: () => void
}

const NONE = '— none —'

// One-agent mode of the run modal: configuration (engine · agent · skill · system
// prompt · mode) + a message box. "Send to agent" posts the message to the board
// AND runs the configured agent on it. Mode lives in a pinned band so it stays
// visible no matter how far the config scrolls.
export function AgentForm({ running, onRun, onClose }: Props): JSX.Element {
  const [engine, setEngine] = useState<string>('claude')
  const [agent, setAgent] = useState<string>('')
  const [skill, setSkill] = useState<string>('')
  const [sysName, setSysName] = useState<string>('')   // '' = none
  const [sysText, setSysText] = useState<string>('')   // editable system-prompt text
  const [interactive, setInteractive] = useState(false)
  const [progress, setProgress] = useState<string>('normal')
  const [message, setMessage] = useState<string>('')
  const [previewOpen, setPreviewOpen] = useState(false)
  const [abilities, setAbilities] = useState<Ability[]>([])
  const [composedBody, setComposedBody] = useState<string | null>(null)
  const [composedSegments, setComposedSegments] = useState<ComposedSegment[]>([])

  // Full agent/skill lists from the real core/ dirs (fall back to common picks).
  const projectPath = useStore((st) => st.projectPath)
  const setMdEditorPath = useUiStore((st) => st.setMdEditorPath)
  const setActivePanel = useUiStore((st) => st.setActivePanel)
  const agentCatalog = useAgentCatalog(projectPath)
  const skillCatalog = useSkillCatalog(projectPath)

  // System-prompt dropdown merges the built-in starters with the user's DB-backed
  // 'system' library prompts; ＋Save persists the current editable text back.
  const sysBuiltins = useMemo(
    () => SYSTEM_PROMPTS.map((p) => ({ name: p.name, label: p.name, hint: p.prompt, prompt: p.prompt })),
    [],
  )
  const { presets: mergedSys, addPreset: addSysPreset } = useMergedPresets(sysBuiltins, {
    kind: 'preset',
    category: 'system',
    projectRoot: projectPath,
  })
  const agentNames = agentCatalog.length ? agentCatalog.map((i) => i.name) : [...AGENTS]
  const skillNames = skillCatalog.length ? skillCatalog.map((i) => i.name) : [...SKILLS]

  const engineOptions: BoardSelectOption[] = ENGINES.map((en) => ({ value: en.value, label: en.label }))
  const agentOptions: BoardSelectOption[] = [{ value: '', label: NONE }, ...agentNames.map((a) => ({ value: a, label: a }))]
  const skillOptions: BoardSelectOption[] = [{ value: '', label: NONE }, ...skillNames.map((sk) => ({ value: sk, label: sk }))]
  const sysOptions: BoardSelectOption[] = [
    { value: '', label: NONE },
    ...mergedSys.map((p) => ({ value: p.name, label: p.name, hint: p.prompt })),
  ]
  const progressOptions: BoardSelectOption[] = PROGRESS_LEVELS.map((p) => ({ value: p.value, label: p.label }))

  // Prompt previews for the current agent/skill — read the real core/ .md.
  const agentContent = usePromptContent(
    agent, 'src/pathly_data/core/agents', agentCatalog, AGENT_FILE_PATHS, {}, projectPath,
  )
  const skillContent = usePromptContent(
    skill, 'src/pathly_data/core/skills', skillCatalog, SKILL_FILE_PATHS, SKILL_PROMPTS, projectPath,
  )

  const agentMdEditorPath = agent && projectPath
    ? (() => {
      const rel = findPath(agent, agentCatalog, AGENT_FILE_PATHS)
      return rel ? `${projectPath}/src/pathly_data/core/agents/${rel}.md` : null
    })()
    : null
  const skillMdEditorPath = skill && projectPath
    ? (() => {
      const rel = findPath(skill, skillCatalog, SKILL_FILE_PATHS)
      return rel ? `${projectPath}/src/pathly_data/core/skills/${rel}.md` : null
    })()
    : null

  function openMdEditor(path: string | null): void {
    if (!path) return
    setMdEditorPath(path)
    setActivePanel('markdown-editor')
    onClose()
  }

  // Selecting a preset seeds the editable text; the user can then tweak it inline.
  function pickSys(name: string): void {
    setSysName(name)
    setSysText(mergedSys.find((p) => p.name === name)?.prompt ?? '')
  }

  // A run needs something to act on: a typed message, a skill (which encodes the
  // task), or a system prompt (a directive). Any one of the three enables Send.
  const canSend = !running && (message.trim().length > 0 || skill !== '' || sysName !== '')

  // When the gate opens with a skill, compose the REAL skill body (+ abilities) so the Sections
  // editor operates on the actual prompt and a trim can be sent verbatim as the override.
  useEffect(() => {
    if (!previewOpen || !skill) {
      setComposedBody(null)
      setComposedSegments([])
      return
    }
    let cancelled = false
    void composeSkillPrompt(skill, {
      adapter: engine,
      abilityIds: abilities.map((a) => a.id),
      projectRoot: projectPath,
    }).then((r) => {
      if (cancelled) return
      setComposedBody(r?.prompt ?? null)
      setComposedSegments(r?.segments ?? [])
    })
    return () => {
      cancelled = true
    }
  }, [previewOpen, skill, engine, abilities, projectPath])

  // F2 gate preview. With a skill, show the REAL composed body (skill + abilities) — it's
  // Sections-trimmable and sent verbatim as the override. Message/System/Agent are separate cfg
  // fields (shown as meta), so they compose around the body at spawn without duplication.
  const previewPrompt = useMemo(() => {
    if (skill && composedBody) return composedBody
    const parts: string[] = []
    if (message.trim()) parts.push(`# Task\n\n${message.trim()}`)
    if (sysText.trim()) parts.push(`# System prompt\n\n${sysText.trim()}`)
    if (skill) parts.push(`# Skill: \`${skill}\`\n\n_The skill body + Pathly fragments compose at spawn._`)
    for (const ab of abilities) parts.push(`# Ability: ${ab.label}\n\n${ab.body}`)
    if (agent) parts.push(`# Agent: \`${agent}\`\n\n_The agent persona is applied at spawn._`)
    parts.push('---\n_Board context is retrieved and prepended when the agent runs, so it is not shown verbatim above._')
    return parts.join('\n\n')
  }, [message, sysText, skill, agent, abilities, composedBody])

  function send(): void {
    if (!canSend) return
    setPreviewOpen(true)
  }

  function confirmSend(finalPrompt?: string, sectionsUsed?: boolean): void {
    // ONLY a confirmed Sections config overrides composition — otherwise leave it to the
    // server (skill + fragments + abilities). Sending the client prompt on every run would
    // risk shipping a body without the platform fragments (no AGENT_DONE → the run vanishes
    // from RECENT and goes unbilled).
    const override = sectionsUsed && skill && composedBody ? finalPrompt : undefined
    onRun({
      adapter: engine,
      agent: agent || undefined,
      skill: skill || undefined,
      systemPrompt: sysText || undefined,
      interactive,
      // Progress cadence only applies headless — interactive shows the terminal.
      progress: interactive ? undefined : progress,
      message: message.trim(),
      abilityIds: abilities.length ? abilities.map((a) => a.id) : undefined,
      promptOverride: override,
    })
    setMessage('')
    setPreviewOpen(false)
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
        <BoardSelect id="sa-engine" ariaLabel="Engine" value={engine} options={engineOptions} onChange={setEngine} />

        <label className={s.label} htmlFor="sa-agent">Agent</label>
        <BoardSelect id="sa-agent" ariaLabel="Agent" value={agent} options={agentOptions} onChange={setAgent} placeholder={NONE} />
        {agent && (
          <PromptBanner
            content={agentContent}
            mdEditorPath={agentMdEditorPath}
            onOpenMdEditor={() => openMdEditor(agentMdEditorPath)}
          />
        )}

        <label className={s.label} htmlFor="sa-skill">Skill</label>
        <BoardSelect id="sa-skill" ariaLabel="Skill" value={skill} options={skillOptions} onChange={setSkill} placeholder={NONE} />
        {skill && (
          <PromptBanner
            content={skillContent}
            mdEditorPath={skillMdEditorPath}
            onOpenMdEditor={() => openMdEditor(skillMdEditorPath)}
          />
        )}

        <label className={s.label}>Abilities <span className={s.optional}>· optional approach / domain packs</span></label>
        <AbilityToggles
          projectRoot={projectPath}
          selectedIds={abilities.map((a) => a.id)}
          onChange={setAbilities}
        />

        <label className={s.label} htmlFor="sa-sys">System prompt</label>
        <BoardSelect id="sa-sys" ariaLabel="System prompt" value={sysName} options={sysOptions} onChange={pickSys} placeholder={NONE} />
        {sysName && (
          <PromptBanner editable editValue={sysText} onEditChange={setSysText} />
        )}
        {sysText.trim() && <PresetAddRow onAdd={(name) => addSysPreset(name, sysText)} />}

        {!interactive && (
          <>
            <label className={s.label} htmlFor="sa-progress">Board updates <span className={s.optional}>· how often the agent posts progress</span></label>
            <BoardSelect id="sa-progress" ariaLabel="Board updates" value={progress} options={progressOptions} onChange={setProgress} />
          </>
        )}

        <p className={s.modeHint}>
          Sending posts your message to the board and runs the agent on it. The board’s own input box just adds a note — it doesn’t call an agent.
        </p>
      </div>

      <div className={s.modeBand}>
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

      {previewOpen && (
        <SendPreviewModal
          title="Run on this board"
          engineLabel={ENGINES.find((e) => e.value === engine)?.label ?? engine}
          fileName={interactive ? 'interactive' : 'headless'}
          prompt={previewPrompt}
          readOnly
          headingLayers={headingLayers(composedSegments)}
          meta={[
            ...(message.trim() ? [{ label: 'Message', value: message.trim().slice(0, 50) }] : []),
            ...(sysName ? [{ label: 'System', value: sysName }] : []),
            ...(abilities.length ? [{ label: 'Abilities', value: String(abilities.length) }] : []),
          ]}
          submitLabel="Send to agent"
          onSubmit={(finalPrompt, sectionsUsed) => confirmSend(finalPrompt, sectionsUsed)}
          onCancel={() => setPreviewOpen(false)}
        />
      )}
    </>
  )
}
