import { useEffect, useState } from 'react'
import { listDir, getAppRoot } from '../../../services/pathlyApi'
import styles from './BlockAuthorForm.module.css'

const CORE_BLOCK_NAMES = ['full-build', 'lite-build', 'review-strict']

/**
 * Optional metadata for known fragments.
 * Add an entry here when a new fragment has a host requirement.
 * The list of fragments itself is loaded dynamically from disk.
 */
const FRAGMENT_META: Record<string, { requires?: string }> = {
  'spawn-rules': { requires: 'can_spawn' },
}

interface FragmentEntry {
  id: string
  label: string
}

interface Props {
  onSave: (name: string, entries: string[]) => void
  onCancel: () => void
}

export function BlockAuthorForm({ onSave, onCancel }: Props): JSX.Element {
  const [name, setName] = useState('')
  const [selected, setSelected] = useState<string[]>([])
  const [nameError, setNameError] = useState('')
  const [fragmentError, setFragmentError] = useState('')
  const [fragments, setFragments] = useState<FragmentEntry[]>([])
  const [loadError, setLoadError] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function loadFragments(): Promise<void> {
      try {
        const appRoot = await getAppRoot()
        const dir = `${appRoot}/src/pathly_data/core/skills/fragments`
        const files = await listDir(dir)
        if (cancelled) return
        const entries: FragmentEntry[] = files
          .filter((f) => f.endsWith('.md') && !f.startsWith('_'))
          .map((f) => f.replace(/\.md$/, ''))
          .sort()
          .map((id) => {
            const meta = FRAGMENT_META[id]
            const label = meta?.requires ? `${id} (requires: ${meta.requires})` : id
            return { id, label }
          })
        setFragments(entries)
      } catch {
        if (!cancelled) setLoadError(true)
      }
    }
    void loadFragments()
    return () => { cancelled = true }
  }, [])

  const isDuplicateCore = CORE_BLOCK_NAMES.includes(name.trim())

  function toggleFragment(id: string): void {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((f) => f !== id) : [...prev, id]
    )
    setFragmentError('')
  }

  function handleSubmit(e: React.FormEvent): void {
    e.preventDefault()
    let valid = true
    if (!name.trim()) {
      setNameError('Block name is required.')
      valid = false
    } else {
      setNameError('')
    }
    if (selected.length === 0) {
      setFragmentError('Select at least one fragment.')
      valid = false
    } else {
      setFragmentError('')
    }
    if (!valid) return
    onSave(name.trim(), selected)
  }

  return (
    <form className={styles.root} onSubmit={handleSubmit} noValidate>
      <div className={styles.field}>
        <label className={styles.label} htmlFor="block-name">
          Block name
        </label>
        <input
          id="block-name"
          className={styles.input}
          type="text"
          value={name}
          onChange={(e) => { setName(e.target.value); setNameError('') }}
          aria-label="Block name"
          aria-describedby={nameError ? 'block-name-error' : undefined}
          autoComplete="off"
        />
        {nameError && (
          <span id="block-name-error" className={styles.error} role="alert">
            {nameError}
          </span>
        )}
        {!nameError && isDuplicateCore && (
          <span className={styles.warning} role="status">
            This name shadows a core block ({name.trim()}).
          </span>
        )}
      </div>

      <fieldset className={styles.fieldset}>
        <legend className={styles.legend}>Fragments</legend>
        {loadError && (
          <span className={styles.loadingMsg}>Could not load fragments from disk.</span>
        )}
        {!loadError && fragments.length === 0 && (
          <span className={styles.loadingMsg}>Loading…</span>
        )}
        {fragments.map(({ id, label }) => (
          <label key={id} className={styles.checkRow} htmlFor={`frag-${id}`}>
            <input
              id={`frag-${id}`}
              type="checkbox"
              checked={selected.includes(id)}
              onChange={() => toggleFragment(id)}
            />
            <span className={styles.fragLabel}>{label}</span>
          </label>
        ))}
        {fragmentError && (
          <span className={styles.error} role="alert">
            {fragmentError}
          </span>
        )}
      </fieldset>

      <div className={styles.actions}>
        <button type="button" className={styles.cancelBtn} onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className={styles.saveBtn}>
          Save block
        </button>
      </div>
    </form>
  )
}
