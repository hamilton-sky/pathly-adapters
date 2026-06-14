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
  const defaults = STAGE_DEFAULTS[stage] ?? { agent: 'builder', skill: 'fix/build' }
  const [host, setHost]   = useState<string>('Claude Code')
  const [agent, setAgent] = useState<string>(defaults.agent)
  const [skill, setSkill] = useState<string>(defaults.skill)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved]   = useState(false)

  const projectPath          = useStore((s) => s.projectPath)
  const activeTopic          = useStore((s) => s.activeTopic)
  const setActivePanel       = useStore((s) => s.setActivePanel)
  const setSkillNotebookPath = useUiStore((s) => s.setSkillNotebookPath)

  const agentCatalog = useAgentCatalog(projectPath)
  const skillCatalog = useSkillCatalog(projectPath)
  const agentPathMap = useMemo(
    () => new Map(agentCatalog.map((i) => [i.name, i.path])),
    [agentCatalog],
  )

  // ── Load saved stage config ──────────────────────────────────────────────
  useEffect(() => {
    if (!projectPath || !activeTopic) return
    const params = new URLSearchParams({ project_root: projectPath, feature: activeTopic, stage })
    fetch(`${PATHLY_API_BASE}/flows/stage-config?${params}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((cfg) => {
        if (!cfg) return
        if (cfg.agent)   setAgent(cfg.agent)
        if (cfg.adapter) setHost(ADAPTER_TO_HOST[cfg.adapter] ?? 'Claude Code')
        if (cfg.skill)   setSkill(cfg.skill)
      })
      .catch(() => undefined)
  }, [projectPath, activeTopic, stage])

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
      .then(() => { setHost('Claude Code'); setAgent(defaults.agent); setSkill(defaults.skill) })
      .catch(() => undefined)
  }

  function handleOpenInNotebook(): void {
    const relPath = SKILL_FILE_PATHS[skill] ?? skill
    setSkillNotebookPath(`${projectPath}/src/pathly_data/core/skills/${relPath}.md`)
    setActivePanel('skill-notebook')
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
        <Button variant="ghost" icon={<BookOpen size={14} />} onClick={handleOpenInNotebook}>
          Open skill in Notebook
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
