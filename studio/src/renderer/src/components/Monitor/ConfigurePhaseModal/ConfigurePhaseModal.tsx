/* ──────────────────────────────────────────────────────────────────────────
   ConfigurePhaseModal — CONNECTED container.

   This is the file you drop into your real app as
       src/renderer/src/components/Monitor/ConfigurePhaseModal/ConfigurePhaseModal.tsx

   It owns ALL the app plumbing (store, /flows/stage-config fetches, catalog
   hooks, window.pathly.fs prompt loading, notebook navigation, adapter map)
   and renders the small presentational components from ./components/*.

   Nothing about the look lives here — that's all in the presentational pieces
   and their CSS modules, which read the Pathly design tokens.

   NOTE: the ../../../store · ../../../store/uiStore · ../../../lib/config
   imports resolve in YOUR repo, not in the design-system project — that's why
   this lives under templates/ (uncompiled source-for-copy).
   ────────────────────────────────────────────────────────────────────────── */
import { useState, useEffect, useMemo } from 'react'
import { Settings, BookOpen, Check, X } from 'lucide-react'

// ── App wiring (your real modules) ──────────────────────────────────────────
import { useStore } from '../../../store'
import { useUiStore } from '../../../store/uiStore'
import { PATHLY_API_BASE } from '../../../lib/config'
import {
  CLI_HOSTS, AGENTS, SKILLS,
  HOST_TO_ADAPTER, ADAPTER_TO_HOST,
  SKILL_FILE_PATHS, AGENT_FILE_PATHS, STAGE_DEFAULTS, SKILL_PROMPTS,
  DEFAULT_SKILL_PATHS,
} from './configurePhaseModalData'
import { useAgentCatalog, useSkillCatalog } from './hooks/usePhaseModalCatalog'
import { CatalogDropdown } from './CatalogDropdown/CatalogDropdown'
import { AbilityToggles } from '../../shared/AbilityToggles/AbilityToggles'
import { StageSectionsButton } from './StageSectionsButton/StageSectionsButton'

// ── Presentational design-system pieces ─────────────────────────────────────
import { Modal } from './components/Modal/Modal'
import { StatePill } from './components/StatePill/StatePill'
import { AssemblyRecipe } from './components/AssemblyRecipe/AssemblyRecipe'
import { ChipGroup } from './components/ChipGroup/ChipGroup'
import { SectionLabel } from './components/SectionLabel/SectionLabel'
import { PromptPreview } from './components/PromptPreview/PromptPreview'
import { Button } from './components/Button/Button'
import type { StageName } from './types'

import styles from './ConfigurePhaseModal.module.css'

interface Props {
  stage: string
  onClose: () => void
}

export function ConfigurePhaseModal({ stage, onClose }: Props): JSX.Element {
  const projectPath          = useStore((s) => s.projectPath)
  const activeTopic          = useStore((s) => s.activeTopic)
  const setActivePanel       = useStore((s) => s.setActivePanel)
  const flowAgent            = useStore((s) => s.stageRoles[stage])
  const flowSkill            = useStore((s) => s.stageSkills[stage])
  const setMdEditorPath = useUiStore((s) => s.setMdEditorPath)

  // Defaults come from the ACTIVE flow's role_map/agent_map, so debug, explore, and
  // consultation stages get their real agent + skill. The static team map is only a
  // fallback for stages the flow didn't declare (or when the flow YAML failed to load).
  const staticDefault = STAGE_DEFAULTS[stage] ?? { agent: 'builder', skill: 'fix/build' }
  const defaults = {
    agent: flowAgent ?? staticDefault.agent,
    skill: flowSkill ?? staticDefault.skill,
  }

  const [host, setHost]   = useState<string>('Claude Code')
  const [agent, setAgent] = useState<string>(defaults.agent)
  const [skill, setSkill] = useState<string>(defaults.skill)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved]   = useState(false)
  // flow-phase-inspector (#5): per-stage layer-3 abilities + excluded section headings.
  // Both persist as the SELECTION on stage_configs and apply fresh at spawn (build_prompt).
  const [abilityIds, setAbilityIds] = useState<string[]>([])
  const [excludedSections, setExcludedSections] = useState<string[]>([])

  const agentCatalog = useAgentCatalog(projectPath)
  const skillCatalog = useSkillCatalog(projectPath)
  const agentPathMap = useMemo(
    () => new Map(agentCatalog.map((i) => [i.name, i.path])),
    [agentCatalog],
  )

  // ── Reset to the stage's flow defaults, then overlay any saved override ───
  useEffect(() => {
    setHost('Claude Code')
    setAgent(defaults.agent)
    setSkill(defaults.skill)
    setAbilityIds([])
    setExcludedSections([])
    if (!projectPath || !activeTopic) return
    const params = new URLSearchParams({ project_root: projectPath, feature: activeTopic, stage })
    fetch(`${PATHLY_API_BASE}/flows/stage-config?${params}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((cfg) => {
        if (!cfg) return
        if (cfg.agent)   setAgent(cfg.agent)
        if (cfg.adapter) setHost(ADAPTER_TO_HOST[cfg.adapter] ?? 'Claude Code')
        if (cfg.skill)   setSkill(cfg.skill)
        if (Array.isArray(cfg.ability_ids)) setAbilityIds(cfg.ability_ids)
        if (Array.isArray(cfg.excluded_sections)) setExcludedSections(cfg.excluded_sections)
      })
      .catch(() => undefined)
  }, [projectPath, activeTopic, stage, defaults.agent, defaults.skill])

  // ── Live skill / agent markdown for the preview ──────────────────────────
  const [loadedSkillText, setLoadedSkillText] = useState<string | null>(null)
  useEffect(() => {
    setLoadedSkillText(null)
    if (!projectPath) return
    const relPath = SKILL_FILE_PATHS[skill] ?? skill
    window.pathly.fs.read(`${projectPath}/src/pathly_data/core/skills/${relPath}.md`)
      .then((text) => setLoadedSkillText(text ?? null))
      .catch(() => setLoadedSkillText(null))
  }, [skill, projectPath])

  const [loadedAgentText, setLoadedAgentText] = useState<string | null>(null)
  useEffect(() => {
    setLoadedAgentText(null)
    if (!projectPath) return
    const relPath = AGENT_FILE_PATHS[agent] ?? agentPathMap.get(agent) ?? agent
    window.pathly.fs.read(`${projectPath}/src/pathly_data/core/agents/${relPath}.md`)
      .then((text) => setLoadedAgentText(text ?? null))
      .catch(() => setLoadedAgentText(null))
  }, [agent, projectPath, agentPathMap])

  const basePreview = loadedSkillText ?? SKILL_PROMPTS[skill] ?? `# ${skill}\n\nNo preview available.`
  const preview     = basePreview.replace(/^Host: [^\n]+/m, `Host: ${host} · Agent: ${agent}`)
  const isModified  = host !== 'Claude Code' || agent !== defaults.agent || skill !== defaults.skill
    || abilityIds.length > 0 || excludedSections.length > 0

  // ── Actions ──────────────────────────────────────────────────────────────
  function handleApply(): void {
    if (!projectPath || !activeTopic) { onClose(); return }
    setSaving(true)
    fetch(`${PATHLY_API_BASE}/flows/stage-config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_root: projectPath,
        feature: activeTopic,
        stage,
        agent,
        adapter: HOST_TO_ADAPTER[host] ?? host,
        skill,
        ability_ids: abilityIds,
        excluded_sections: excludedSections,
      }),
    })
      .then(() => { setSaving(false); setSaved(true); setTimeout(() => setSaved(false), 2000) })
      .catch(() => setSaving(false))
  }

  function handleReset(): void {
    if (!projectPath || !activeTopic) return
    fetch(`${PATHLY_API_BASE}/flows/stage-config`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_root: projectPath, feature: activeTopic, stage }),
    })
      .then(() => {
        setHost('Claude Code'); setAgent(defaults.agent); setSkill(defaults.skill)
        setAbilityIds([]); setExcludedSections([])
      })
      .catch(() => undefined)
  }

  function handleOpenInMdEditor(): void {
    const relPath = SKILL_FILE_PATHS[skill] ?? skill
    setMdEditorPath(`${projectPath}/src/pathly_data/core/skills/${relPath}.md`)
    setActivePanel('markdown-editor')
    onClose()
  }

  // ── Render — presentational pieces, app data ─────────────────────────────
  return (
    <Modal onClose={onClose} ariaLabel={`Configure ${stage} phase`}>
      <header className={styles.header}>
        <span className={styles.gear}><Settings size={16} /></span>
        <span className={styles.title}>Configure phase</span>
        <span className={styles.spacer} />
        <StatePill state={stage as StageName} />
        <button type="button" className={styles.close} onClick={onClose} aria-label="Close">
          <X size={16} />
        </button>
      </header>

      <div className={styles.body}>
        <AssemblyRecipe host={host} agent={agent} skill={skill} />

        <ChipGroup
          label="CLI Host"
          variant="host"
          options={[...CLI_HOSTS]}
          value={host}
          onSelect={setHost}
        />

        <ChipGroup
          label="Agent"
          variant="agent"
          mono
          options={[...AGENTS]}
          value={agent}
          onSelect={setAgent}
          trailing={
            <CatalogDropdown
              catalog={agentCatalog}
              isExcluded={(item) =>
                (AGENTS as readonly string[]).includes(item.name) || item.name === agent
              }
              onSelect={(item) => setAgent(item.name)}
              color="agent"
            />
          }
        />

        <ChipGroup
          label="Skill"
          variant="skill"
          mono
          options={[...SKILLS]}
          value={skill}
          onSelect={setSkill}
          trailing={
            <CatalogDropdown
              catalog={skillCatalog}
              isExcluded={(item) =>
                DEFAULT_SKILL_PATHS.has(item.path) || item.name === skill
              }
              onSelect={(item) => setSkill(item.name)}
              color="skill"
            />
          }
        />

        <div>
          <SectionLabel>Abilities</SectionLabel>
          <AbilityToggles
            projectRoot={projectPath}
            selectedIds={abilityIds}
            onChange={(rows) => setAbilityIds(rows.map((r) => r.id))}
          />
        </div>

        <div>
          <SectionLabel>Sections</SectionLabel>
          <StageSectionsButton
            projectRoot={projectPath}
            skill={skill}
            abilityIds={abilityIds}
            excludedSections={excludedSections}
            onChange={setExcludedSections}
          />
        </div>

        <div>
          <SectionLabel>Prompt Preview</SectionLabel>
          <PromptPreview
            label={`${skill} · ${agent} · ${host}`}
            skillPrompt={preview}
            agentPrompt={loadedAgentText ?? undefined}
            isModified={isModified}
          />
        </div>
      </div>

      <footer className={styles.footer}>
        <Button variant="ghost" icon={<BookOpen size={14} />} onClick={handleOpenInMdEditor}>
          Open skill in Markdown Editor
        </Button>
        <span className={styles.spacer} />
        <Button variant="quiet" onClick={handleReset}>Reset to default</Button>
        <Button variant="quiet" onClick={onClose}>Cancel</Button>
        <Button variant="primary" icon={<Check size={14} />} onClick={handleApply} disabled={saving}>
          {saved ? 'Saved' : 'Apply'}
        </Button>
      </footer>
    </Modal>
  )
}
