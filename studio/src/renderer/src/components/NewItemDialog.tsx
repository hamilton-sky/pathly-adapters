import { useEffect, useRef, useState } from 'react'
import { useTheme } from '../useTheme'
import type { Theme } from '../theme'
import type { PathlyItem } from '../types'

interface Props {
  type: 'skill' | 'agent'
  dir: string
  onClose: () => void
  onCreated: (item: PathlyItem) => void
}

function makeStyles(t: Theme): Record<string, React.CSSProperties> {
  return {
    overlay: {
      position: 'fixed',
      inset: 0,
      backgroundColor: 'rgba(0,0,0,0.6)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000
    },
    card: {
      width: '400px',
      backgroundColor: t.bgMantle,
      border: `1px solid ${t.bgSurface0}`,
      borderRadius: '8px',
      padding: '24px',
      display: 'flex',
      flexDirection: 'column',
      gap: '16px'
    },
    title: {
      fontSize: '16px',
      fontWeight: 600,
      color: t.textPrimary,
      margin: 0
    },
    input: {
      width: '100%',
      boxSizing: 'border-box' as const,
      backgroundColor: t.bgBase,
      border: `1px solid ${t.bgSurface0}`,
      borderRadius: '4px',
      color: t.textPrimary,
      fontSize: '13px',
      padding: '8px 10px',
      outline: 'none',
      fontFamily: 'monospace'
    },
    error: {
      color: t.red,
      fontSize: '12px'
    },
    btnRow: {
      display: 'flex',
      justifyContent: 'flex-end',
      gap: '8px'
    },
    cancelBtn: {
      background: 'none',
      border: `1px solid ${t.bgSurface1}`,
      borderRadius: '4px',
      color: t.textSecondary,
      cursor: 'pointer',
      padding: '6px 16px',
      fontSize: '13px'
    },
    createBtn: {
      background: t.accent,
      border: 'none',
      borderRadius: '4px',
      color: t.bgBase,
      cursor: 'pointer',
      padding: '6px 16px',
      fontSize: '13px',
      fontWeight: 600
    }
  }
}

export function NewItemDialog({ type, dir, onClose, onCreated }: Props): JSX.Element {
  const t = useTheme()
  const styles = makeStyles(t)
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
    function handleKeyDown(e: KeyboardEvent): void {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  async function handleCreate(): Promise<void> {
    const trimmed = name.trim()
    if (!trimmed) {
      setError('Name is required')
      return
    }
    if (!/^[a-zA-Z0-9-]+$/.test(trimmed)) {
      setError('Name must be alphanumeric with hyphens only')
      return
    }
    setError(null)

    const filePath = `${dir}/${trimmed}.md`
    const content =
      type === 'skill'
        ? `# ${trimmed}\n\n## Description\n\n[Describe what this skill does]\n\n## Instructions\n\n`
        : `# ${trimmed}\n\n## Role\n\n[Describe the agent role]\n\n## Instructions\n\n`

    try {
      await window.pathly.fs.write(filePath, content)
      onCreated({ name: `${trimmed}.md`, path: filePath, type })
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  function handleKeyDown(e: React.KeyboardEvent): void {
    if (e.key === 'Enter') handleCreate()
  }

  const title = type === 'skill' ? 'New Skill' : 'New Agent'
  const placeholder = type === 'skill' ? 'my-skill' : 'my-agent'

  return (
    <div style={styles.overlay} onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div style={styles.card}>
        <h2 style={styles.title}>{title}</h2>
        <input
          ref={inputRef}
          style={styles.input}
          type="text"
          placeholder={placeholder}
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        {error && <div style={styles.error}>{error}</div>}
        <div style={styles.btnRow}>
          <button style={styles.cancelBtn} onClick={onClose}>Cancel</button>
          <button style={styles.createBtn} onClick={handleCreate}>Create</button>
        </div>
      </div>
    </div>
  )
}
