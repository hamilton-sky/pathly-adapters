import { useEffect, useRef, useState } from 'react'
import type { PathlyItem } from '../types'
import { writeFile } from '../services/pathlyApi'
import { useFocusTrap } from '../hooks/useFocusTrap'
import styles from './NewItemDialog.module.css'

interface Props {
  type: 'skill' | 'agent' | 'template' | 'debug' | 'explore'
  dir: string
  onClose: () => void
  onCreated: (item: PathlyItem) => void
}

const ADAPTER_OPTIONS = ['claude', 'codex', 'copilot']

// Brand colours — intentionally static, not theme-derived
const ADAPTER_COLORS: Record<string, { color: string; bg: string; border: string }> = {
  claude:  { color: '#E07535', bg: 'rgba(224,117,53,0.12)',  border: 'rgba(224,117,53,0.5)'  },
  codex:   { color: '#0EA5E9', bg: 'rgba(14,165,233,0.12)',  border: 'rgba(14,165,233,0.5)'  },
  copilot: { color: '#8888AA', bg: 'rgba(136,136,170,0.12)', border: 'rgba(136,136,170,0.5)' },
}

function chipVars(active: boolean, meta: typeof ADAPTER_COLORS['claude']): React.CSSProperties {
  return active
    ? { '--chip-color': meta.color, '--chip-bg': meta.bg, '--chip-border': meta.border, '--chip-dot-color': meta.color } as React.CSSProperties
    : {}
}

function buildSkillFrontmatter(name: string, description: string, adapters: string[], tools: string[]): string {
  const lines = [
    `name: ${name}`,
    `description: ${description || ''}`,
    adapters.length > 0
      ? `adapters:\n${adapters.map((a) => `  - ${a}`).join('\n')}`
      : 'adapters: []',
    tools.length > 0
      ? `tools:\n${tools.map((t) => `  - ${t}`).join('\n')}`
      : 'tools: []',
  ]
  return `---\n${lines.join('\n')}\n---\n`
}

export function NewItemDialog({ type, dir, onClose, onCreated }: Props): JSX.Element {
  const inputRef = useRef<HTMLInputElement>(null)
  const cardRef  = useRef<HTMLDivElement>(null)
  useFocusTrap(cardRef)

  const [name, setName]           = useState('')
  const [description, setDesc]    = useState('')
  const [adapters, setAdapters]   = useState<string[]>(['claude'])
  const [toolsRaw, setToolsRaw]   = useState('')
  const [subdirName, setSubdir]   = useState('')
  const [error, setError]         = useState<string | null>(null)

  useEffect(() => {
    inputRef.current?.focus()
    function onKey(e: KeyboardEvent): void { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  function toggleAdapter(adapter: string): void {
    setAdapters((prev) => prev.includes(adapter) ? prev.filter((a) => a !== adapter) : [...prev, adapter])
  }

  async function handleCreate(): Promise<void> {
    const trimmed = name.trim()
    if (!trimmed) { setError('Name is required'); return }
    if (!/^[a-zA-Z0-9-_]+$/.test(trimmed)) { setError('Alphanumeric, hyphens and underscores only'); return }
    setError(null)

    let filePath: string
    let content: string

    if (type === 'skill') {
      const tools = toolsRaw.split(',').map((s) => s.trim()).filter(Boolean)
      filePath = `${dir}/${trimmed}.md`
      content  = buildSkillFrontmatter(trimmed, description.trim(), adapters, tools)
              + `\n# ${trimmed}\n\n## Instructions\n\n[Describe what this skill does step by step]\n`
    } else if (type === 'template') {
      const subdir = subdirName.trim() || 'general'
      filePath = `${dir}/${subdir}/${trimmed}.md`
      content  = `# ${trimmed}\n\n[Template content here]\n`
    } else if (type === 'explore') {
      filePath = `${dir}/${trimmed}/EXPLORE.md`
      content  = `# Exploration — ${trimmed}\n\n## Question\n\n[What do you want to explore?]\n\n## Scope\n\n[Files, layers, or components in scope]\n\n## Out of scope\n\n[What to skip]\n\n## Success criterion\n\n[How we'll know the exploration is complete]\n`
    } else if (type === 'debug') {
      filePath = `${dir}/${trimmed}/DEBUG.md`
      content  = `# Debug — ${trimmed}\n\n## Symptom\n\n[What is the observed behavior?]\n\n## Expected\n\n[What should happen?]\n\n## Repro steps\n\n1. \n\n## Hypotheses\n\n- \n`
    } else {
      filePath = `${dir}/${trimmed}.md`
      content  = `---\nname: ${trimmed}\ndescription: ${description.trim()}\n---\n\n# ${trimmed}\n\n## Role\n\n[Describe the agent role]\n\n## Instructions\n\n`
    }

    try {
      await writeFile(filePath, content)
      const itemName = (type === 'explore' || type === 'debug')
        ? filePath.split('/').slice(-2).join('/')
        : `${trimmed}.md`
      onCreated({ name: itemName, path: filePath, type })
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const titles = { skill: 'New Skill', agent: 'New Agent', template: 'New Template', explore: 'New Exploration', debug: 'New Debug Session' }
  const namePH = { skill: 'my-skill',  agent: 'my-agent',  template: 'my-template',  explore: 'my-exploration', debug: 'my-bug'          }

  return (
    <div className={styles.overlay} onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div
        ref={cardRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-item-dialog-title"
        className={styles.card}
      >
        <div id="new-item-dialog-title" className={styles.header}>{titles[type]}</div>

        <div className={styles.body}>
          <div className={styles.fieldGroup}>
            <label className={styles.label}>Name</label>
            <input
              ref={inputRef}
              className={`${styles.input} ${styles.inputMono}`}
              type="text"
              placeholder={namePH[type]}
              value={name}
              data-label="Item Name"
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') void handleCreate() }}
            />
          </div>

          {(type === 'skill' || type === 'agent') && (
            <div className={styles.fieldGroup}>
              <label className={styles.label}>Description</label>
              <input
                className={styles.input}
                type="text"
                placeholder={type === 'skill' ? 'Continue active pipeline feature' : 'Agent role description'}
                value={description}
                data-label="Item Description"
                onChange={(e) => setDesc(e.target.value)}
              />
            </div>
          )}

          {type === 'skill' && (
            <>
              <div className={styles.fieldGroup}>
                <label className={styles.label}>Adapters</label>
                <div className={styles.chips}>
                  {ADAPTER_OPTIONS.map((adapter) => {
                    const active = adapters.includes(adapter)
                    const meta   = ADAPTER_COLORS[adapter]
                    return (
                      <button
                        key={adapter}
                        type="button"
                        role="switch"
                        aria-checked={active ? 'true' : 'false'}
                        className={styles.chip}
                        style={chipVars(active, meta)}
                        onClick={() => toggleAdapter(adapter)}
                        title={active ? `Remove ${adapter}` : `Add ${adapter}`}
                      >
                        <span className={styles.chipDot} />
                        {adapter}
                      </button>
                    )
                  })}
                </div>
              </div>

              <div className={styles.fieldGroup}>
                <label className={styles.label}>Tools</label>
                <input
                  className={styles.input}
                  type="text"
                  placeholder="Bash, Read, Glob, Grep, TodoWrite, Agent"
                  value={toolsRaw}
                  onChange={(e) => setToolsRaw(e.target.value)}
                />
              </div>
            </>
          )}

          {type === 'template' && (
            <div className={styles.fieldGroup}>
              <label className={styles.label}>Category (subfolder)</label>
              <input
                className={`${styles.input} ${styles.inputMono}`}
                type="text"
                placeholder="general"
                value={subdirName}
                data-label="Subdirectory"
                onChange={(e) => setSubdir(e.target.value)}
              />
            </div>
          )}

          {error && <div className={styles.error}>{error}</div>}
        </div>

        <div className={styles.footer}>
          <button type="button" className={styles.cancelBtn} onClick={onClose}>Cancel</button>
          <button type="button" className={styles.createBtn} data-label="Confirm" onClick={() => void handleCreate()}>Create</button>
        </div>
      </div>
    </div>
  )
}
