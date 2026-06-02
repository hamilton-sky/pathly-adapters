import { useState } from 'react'
import styles from './BlockAuthorForm.module.css'

const CORE_BLOCK_NAMES = ['full-build', 'lite-build', 'review-strict']

const FRAGMENTS: { id: string; label: string }[] = [
  { id: 'progress-logging', label: 'progress-logging' },
  { id: 'completion-report', label: 'completion-report' },
  { id: 'scout-choreography', label: 'scout-choreography' },
  { id: 'feedback-protocol', label: 'feedback-protocol' },
  { id: 'spawn-rules', label: 'spawn-rules (requires: can_spawn)' },
]

interface Props {
  onSave: (name: string, entries: string[]) => void
  onCancel: () => void
}

export function BlockAuthorForm({ onSave, onCancel }: Props): JSX.Element {
  const [name, setName] = useState('')
  const [selected, setSelected] = useState<string[]>([])
  const [nameError, setNameError] = useState('')
  const [fragmentError, setFragmentError] = useState('')

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
        {FRAGMENTS.map(({ id, label }) => (
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
