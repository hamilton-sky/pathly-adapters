import { useEffect, useRef, useState } from 'react'
import { useStore } from '../../store'
import { readFile, writeFile } from '../../services/pathlyApi'
import type { FrontmatterValues } from '../../types'
import { ConfigForm } from './ConfigForm'
import { MarkdownEditor } from './MarkdownEditor'
import { MarkdownPreview } from './MarkdownPreview'
import styles from './index.module.css'

type TabMode = 'edit' | 'preview' | 'split'

// ── Frontmatter parsing / serialization ────────────────────────────────────

function parseFrontmatter(raw: string): { config: FrontmatterValues; body: string } {
  if (!raw.startsWith('---')) return { config: {} as FrontmatterValues, body: raw }
  const end = raw.indexOf('\n---', 3)
  if (end === -1) return { config: {} as FrontmatterValues, body: raw }
  const config = parseSimpleYaml(raw.slice(4, end).trim())
  const body = raw.slice(end + 4).replace(/^\n/, '')
  return { config, body }
}

function parseSimpleYaml(text: string): FrontmatterValues {
  const result: Record<string, unknown> = {}
  const lines = text.split('\n')
  let i = 0
  while (i < lines.length) {
    const keyMatch = lines[i].match(/^(\w[\w-]*):\s*(.*)$/)
    if (!keyMatch) { i++; continue }
    const [, key, rest] = keyMatch
    const trimmed = rest.trim()
    if (trimmed === '' || trimmed === '|' || trimmed === '>') {
      const items: string[] = []
      i++
      while (i < lines.length && /^\s+-\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s+-\s+/, '').trim())
        i++
      }
      result[key] = items.length > 0 ? items : ''
      continue
    }
    if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
      result[key] = trimmed.slice(1, -1).split(',').map((s) => s.trim().replace(/^['"]|['"]$/g, '')).filter(Boolean)
    } else {
      result[key] = trimmed.replace(/^['"]|['"]$/g, '')
    }
    i++
  }
  return result as unknown as FrontmatterValues
}

function serializeFrontmatter(config: FrontmatterValues): string {
  return Object.entries(config)
    .flatMap(([key, value]) => {
      if (value === undefined || value === null) return []
      if (Array.isArray(value)) {
        return value.length === 0
          ? [`${key}: []`]
          : [`${key}:`, ...value.map((v) => `  - ${v}`)]
      }
      return [`${key}: ${String(value)}`]
    })
    .join('\n')
}

// ── Component ──────────────────────────────────────────────────────────────

export function Editor(): JSX.Element {
  const { selectedItem, markDirty, clearDirty, dirtyItems } = useStore()

  const [config, setConfig] = useState<FrontmatterValues>({} as FrontmatterValues)
  const [body, setBody]     = useState('')
  const [tab, setTab]       = useState<TabMode>('edit')
  const [loading, setLoading]     = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const autoSaveRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const isDirty = selectedItem ? dirtyItems.has(selectedItem.path) : false
  const isSkillOrAgent = selectedItem?.type === 'skill' || selectedItem?.type === 'agent'
  const breadcrumb = selectedItem
    ? `${selectedItem.type.charAt(0).toUpperCase() + selectedItem.type.slice(1)}s / ${selectedItem.name}`
    : ''

  useEffect(() => {
    if (!selectedItem) return
    setLoading(true)
    setSaveError(null)
    readFile(selectedItem.path)
      .then((content) => {
        const parsed = parseFrontmatter(content ?? '')
        setConfig(parsed.config)
        setBody(parsed.body)
      })
      .catch(() => { setConfig({} as FrontmatterValues); setBody('') })
      .finally(() => setLoading(false))
  }, [selectedItem?.path])

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent): void {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); void performSave(body, config) }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  })

  async function performSave(currentBody: string, currentConfig: FrontmatterValues): Promise<void> {
    if (!selectedItem) return
    setSaveError(null)
    const merged = `---\n${serializeFrontmatter(currentConfig)}\n---\n${currentBody}`
    try {
      await writeFile(selectedItem.path, merged)
      clearDirty(selectedItem.path)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err))
    }
  }

  function handleConfigChange(v: FrontmatterValues): void {
    setConfig(v)
    if (selectedItem) markDirty(selectedItem.path)
  }

  function handleBodyChange(v: string): void {
    setBody(v)
    if (selectedItem) markDirty(selectedItem.path)
    if (autoSaveRef.current) clearTimeout(autoSaveRef.current)
    autoSaveRef.current = setTimeout(() => void performSave(v, config), 2000)
  }

  if (loading) {
    return <div className={styles.panel}><div className={styles.message}>Loading…</div></div>
  }

  const tabs: TabMode[] = ['edit', 'preview', 'split']

  return (
    <div className={styles.panel}>
      {/* Toolbar — always at top, matches UX diagram */}
      <div className={styles.toolbar}>
        <div className={styles.tabs}>
          {tabs.map((t_) => (
            <button
              key={t_}
              className={tab === t_ ? styles.tabActive : styles.tab}
              onClick={() => setTab(t_)}
            >
              {t_ === 'split' ? '⊟ Split' : t_.charAt(0).toUpperCase() + t_.slice(1)}
            </button>
          ))}
        </div>
        <span className={styles.breadcrumb}>{breadcrumb}</span>
        <div className={styles.actions}>
          {saveError && <span className={styles.error}>{saveError}</span>}
          <button
            className={`${styles.saveBtn} ${isDirty ? '' : styles.saveBtnClean}`}
            onClick={() => void performSave(body, config)}
          >
            {isDirty ? 'Save ●' : 'Saved'}
          </button>
        </div>
      </div>

      {/* Configuration card — only for skills/agents, compact in preview/split */}
      {isSkillOrAgent && (
        <ConfigForm
          values={config}
          onChange={handleConfigChange}
          compact={tab !== 'edit'}
        />
      )}

      {/* Content area */}
      <div className={styles.editorArea}>
        {tab === 'edit' && (
          <div className={styles.full}>
            <MarkdownEditor value={body} onChange={handleBodyChange} />
          </div>
        )}
        {tab === 'preview' && (
          <div className={styles.full}>
            <MarkdownPreview content={body} />
          </div>
        )}
        {tab === 'split' && (
          <div className={styles.splitRow}>
            <div className={styles.half}>
              <MarkdownEditor value={body} onChange={handleBodyChange} />
            </div>
            <div className={styles.splitDivider} />
            <div className={styles.half}>
              <MarkdownPreview content={body} />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
