import { useEffect, useState } from 'react'
import { useStore } from '../../store'
import { useTheme } from '../../useTheme'
import type { Theme } from '../../theme'
import { ConfigForm, FrontmatterValues } from './ConfigForm'
import { MarkdownEditor } from './MarkdownEditor'
import { MarkdownPreview } from './MarkdownPreview'

type TabMode = 'edit' | 'preview' | 'split'

function parseFrontmatter(raw: string): { config: FrontmatterValues; body: string } {
  if (!raw.startsWith('---')) {
    return { config: {}, body: raw }
  }
  const end = raw.indexOf('\n---', 3)
  if (end === -1) {
    return { config: {}, body: raw }
  }
  const yamlText = raw.slice(4, end).trim()
  const body = raw.slice(end + 4).replace(/^\n/, '')
  const config = parseSimpleYaml(yamlText)
  return { config, body }
}

function parseSimpleYaml(text: string): FrontmatterValues {
  const result: FrontmatterValues = {}
  const lines = text.split('\n')
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    const keyMatch = line.match(/^(\w[\w-]*):\s*(.*)$/)
    if (!keyMatch) {
      i++
      continue
    }
    const key = keyMatch[1]
    const rest = keyMatch[2].trim()

    if (rest === '' || rest === '|' || rest === '>') {
      const items: string[] = []
      i++
      while (i < lines.length && lines[i].match(/^\s+-\s+/)) {
        items.push(lines[i].replace(/^\s+-\s+/, '').trim())
        i++
      }
      result[key] = items.length > 0 ? items : ''
      continue
    }

    if (rest.startsWith('[') && rest.endsWith(']')) {
      const inner = rest.slice(1, -1)
      result[key] = inner
        .split(',')
        .map((s) => s.trim().replace(/^['"]|['"]$/g, ''))
        .filter(Boolean)
    } else {
      result[key] = rest.replace(/^['"]|['"]$/g, '')
    }
    i++
  }
  return result
}

function serializeFrontmatter(config: FrontmatterValues): string {
  const lines: string[] = []
  for (const [key, value] of Object.entries(config)) {
    if (Array.isArray(value)) {
      if (value.length === 0) {
        lines.push(`${key}: []`)
      } else {
        lines.push(`${key}:`)
        for (const item of value) {
          lines.push(`  - ${item}`)
        }
      }
    } else if (value === undefined || value === null) {
      // skip
    } else {
      lines.push(`${key}: ${String(value)}`)
    }
  }
  return lines.join('\n')
}

function makeStyles(t: Theme): Record<string, React.CSSProperties> {
  return {
    panel: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      backgroundColor: t.bgBase,
      overflow: 'hidden'
    },
    toolbar: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '6px 12px',
      backgroundColor: t.bgMantle,
      borderBottom: `1px solid ${t.bgSurface0}`,
      flexShrink: 0
    },
    tabs: {
      display: 'flex',
      gap: '4px'
    },
    tab: {
      background: 'none',
      border: `1px solid ${t.bgSurface1}`,
      borderRadius: '4px',
      color: t.textSecondary,
      cursor: 'pointer',
      padding: '3px 10px',
      fontSize: '12px'
    },
    tabActive: {
      background: t.bgSurface0,
      border: `1px solid ${t.accent}`,
      borderRadius: '4px',
      color: t.accent,
      cursor: 'pointer',
      padding: '3px 10px',
      fontSize: '12px'
    },
    actions: {
      display: 'flex',
      alignItems: 'center',
      gap: '8px'
    },
    saveBtn: {
      background: t.accent,
      border: 'none',
      borderRadius: '4px',
      color: t.bgBase,
      cursor: 'pointer',
      padding: '4px 14px',
      fontSize: '13px',
      fontWeight: 600
    },
    error: {
      color: t.red,
      fontSize: '12px'
    },
    editorArea: {
      flex: 1,
      overflow: 'hidden',
      display: 'flex'
    },
    full: {
      flex: 1,
      overflow: 'hidden'
    },
    splitRow: {
      flex: 1,
      display: 'flex',
      overflow: 'hidden'
    },
    half: {
      flex: 1,
      overflow: 'hidden'
    },
    divider: {
      width: '1px',
      backgroundColor: t.bgSurface0,
      flexShrink: 0
    },
    message: {
      color: t.textMuted,
      fontSize: '15px',
      margin: 'auto'
    }
  }
}

export function Editor(): JSX.Element {
  const { selectedItem, markDirty, clearDirty } = useStore()
  const t = useTheme()
  const styles = makeStyles(t)
  const [config, setConfig] = useState<FrontmatterValues>({})
  const [body, setBody] = useState('')
  const [tab, setTab] = useState<TabMode>('edit')
  const [loading, setLoading] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => {
    if (!selectedItem) return
    setLoading(true)
    setSaveError(null)
    window.pathly.fs
      .read(selectedItem.path)
      .then((content) => {
        const parsed = parseFrontmatter(content ?? '')
        setConfig(parsed.config)
        setBody(parsed.body)
      })
      .catch(() => {
        setConfig({})
        setBody('')
      })
      .finally(() => setLoading(false))
  }, [selectedItem?.path])

  function handleConfigChange(v: FrontmatterValues): void {
    setConfig(v)
    if (selectedItem) markDirty(selectedItem.path)
  }

  function handleBodyChange(v: string): void {
    setBody(v)
    if (selectedItem) markDirty(selectedItem.path)
  }

  async function handleSave(): Promise<void> {
    if (!selectedItem) return
    setSaveError(null)
    const yaml = serializeFrontmatter(config)
    const merged = `---\n${yaml}\n---\n${body}`
    try {
      await window.pathly.fs.write(selectedItem.path, merged)
      clearDirty(selectedItem.path)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err))
    }
  }

  if (loading) {
    return (
      <div style={styles.panel}>
        <span style={styles.message}>Loading…</span>
      </div>
    )
  }

  return (
    <div style={styles.panel}>
      <ConfigForm values={config} onChange={handleConfigChange} />

      <div style={styles.toolbar}>
        <div style={styles.tabs}>
          <button
            style={tab === 'edit' ? styles.tabActive : styles.tab}
            onClick={() => setTab('edit')}
          >
            Edit
          </button>
          <button
            style={tab === 'preview' ? styles.tabActive : styles.tab}
            onClick={() => setTab('preview')}
          >
            Preview
          </button>
          <button
            style={tab === 'split' ? styles.tabActive : styles.tab}
            onClick={() => setTab('split')}
          >
            ⊟ Split
          </button>
        </div>
        <div style={styles.actions}>
          {saveError && <span style={styles.error}>{saveError}</span>}
          <button style={styles.saveBtn} onClick={handleSave}>
            Save
          </button>
        </div>
      </div>

      <div style={styles.editorArea}>
        {tab === 'edit' && (
          <div style={styles.full}>
            <MarkdownEditor value={body} onChange={handleBodyChange} />
          </div>
        )}
        {tab === 'preview' && (
          <div style={styles.full}>
            <MarkdownPreview content={body} />
          </div>
        )}
        {tab === 'split' && (
          <div style={styles.splitRow}>
            <div style={styles.half}>
              <MarkdownEditor value={body} onChange={handleBodyChange} />
            </div>
            <div style={styles.divider} />
            <div style={styles.half}>
              <MarkdownPreview content={body} />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
