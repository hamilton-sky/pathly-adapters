import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { X, Settings, BookOpen, Check } from 'lucide-react'
import { useStore } from '../../../store'
import { useUiStore } from '../../../store/uiStore'
import { StatePill } from '../../ui/StatePill/StatePill'
import { PATHLY_API_BASE } from '../../../lib/config'
import {
  CLI_HOSTS, AGENTS, SKILLS,
  HOST_TO_ADAPTER, ADAPTER_TO_HOST,
  SKILL_FILE_PATHS, STAGE_DEFAULTS, SKILL_PROMPTS,
} from './configurePhaseModalData'
import styles from './ConfigurePhaseModal.module.css'

interface Props {
  stage: string
  onClose: () => void
}

export function ConfigurePhaseModal({ stage, onClose }: Props): JSX.Element {
  const defaults = STAGE_DEFAULTS[stage] ?? { agent: 'builder', skill: 'fix/build' }
  const [host, setHost]     = useState<string>('Claude Code')
  const [agent, setAgent]   = useState<string>(defaults.agent)
  const [skill, setSkill]   = useState<string>(defaults.skill)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved]   = useState(false)

  const projectPath = useStore((s) => s.projectPath)
  const activeTopic = useStore((s) => s.activeTopic)
  const setActivePanel = useStore((s) => s.setActivePanel)
  const setSkillNotebookPath = useUiStore((s) => s.setSkillNotebookPath)

  useEffect(() => {
    if (!projectPath || !activeTopic) return
    const params = new URLSearchParams({ project_root: projectPath, feature: activeTopic, stage })
    fetch(`${PATHLY_API_BASE}/flows/stage-config?${params}`)
      .then((r) => r.ok ? r.json() : null)
      .then((cfg) => {
        if (!cfg) return
        if (cfg.agent) setAgent(cfg.agent)
        if (cfg.adapter) setHost(ADAPTER_TO_HOST[cfg.adapter] ?? 'Claude Code')
        if (cfg.skill) setSkill(cfg.skill)
      })
      .catch(() => undefined)
  }, [projectPath, activeTopic, stage])

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

  const basePreview = SKILL_PROMPTS[skill] ?? `# ${skill}\n\nNo preview available.`
  const preview = basePreview.replace(/^Host: [^\n]+/m, `Host: ${host} · Agent: ${agent}`)

  return createPortal(
    <div className={styles.backdrop} onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className={styles.modal} role="dialog" aria-modal="true" aria-label={`Configure ${stage} phase`}>
        <div className={styles.header}>
          <Settings size={16} className={styles.gearIcon} />
          <span className={styles.title}>Configure phase</span>
          <span className={styles.subtitle}>— what runs when the pipeline enters this stage</span>
          <StatePill state={stage as Parameters<typeof StatePill>[0]['state']} className={styles.stagePill} />
          <button type="button" className={styles.close} onClick={onClose} aria-label="Close"><X size={16} /></button>
        </div>

        <div className={styles.body}>
          <div className={styles.section}>
            <div className={styles.sectionLabel}>CLI Host</div>
            <div className={styles.chips}>
              {CLI_HOSTS.map((h) => (
                <button key={h} type="button"
                  className={`${styles.chip} ${host === h ? styles.chipActive : ''}`}
                  onClick={() => setHost(h)}>{h}</button>
              ))}
            </div>
          </div>
          <div className={styles.section}>
            <div className={styles.sectionLabel}>Agent</div>
            <div className={styles.chips}>
              {AGENTS.map((a) => (
                <button key={a} type="button"
                  className={`${styles.chip} ${styles.chipMono} ${agent === a ? styles.chipActive : ''}`}
                  onClick={() => setAgent(a)}>{a}</button>
              ))}
            </div>
          </div>
          <div className={styles.section}>
            <div className={styles.sectionLabel}>Skill</div>
            <div className={styles.chips}>
              {SKILLS.map((sk) => (
                <button key={sk} type="button"
                  className={`${styles.chip} ${styles.chipMono} ${skill === sk ? styles.chipActive : ''}`}
                  onClick={() => setSkill(sk)}>{sk}</button>
              ))}
            </div>
          </div>
          <div className={styles.section}>
            <div className={styles.sectionLabel}>Prompt Preview</div>
            <pre className={styles.promptPre}>{preview}</pre>
          </div>
        </div>

        <div className={styles.footer}>
          <button type="button" className={styles.notebookBtn} onClick={handleOpenInNotebook}>
            <BookOpen size={14} />Open skill in Notebook
          </button>
          <span className={styles.footerSpacer} />
          <button type="button" className={styles.resetBtn} onClick={handleReset}>Reset to default</button>
          <button type="button" className={styles.cancelBtn} onClick={onClose}>Cancel</button>
          <button type="button" className={styles.applyBtn} onClick={handleApply} disabled={saving}>
            <Check size={14} />
            {saved ? <span className={styles.savedHint}>Saved</span> : 'Apply'}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
