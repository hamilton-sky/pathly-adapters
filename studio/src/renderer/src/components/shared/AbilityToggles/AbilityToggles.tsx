// AbilityToggles — layer-3: pick optional domain/approach "abilities" (prompt_library
// kind='ability') to STACK onto a run, and create new ones inline. Abilities are the
// voluntary "how it approaches THIS task" layer (React-web vs desktop, TDD-per-task vs
// at-end) — orthogonal to the skill (the task). Selected abilities compose server-side
// (POST /skills/compose ability_ids → extra_segments) AFTER the skill's own fragments.

import { useCallback, useEffect, useState } from 'react'
import { Plus, Check, X } from 'lucide-react'
import { listAbilities, saveAbility, type Ability } from '../../../services/abilities'
import s from './AbilityToggles.module.css'

const CATEGORIES = ['plan', 'build', 'review', 'test'] as const

interface Props {
  projectRoot: string
  /** Currently-selected ability ids ("<category>/<name>"). */
  selectedIds: string[]
  /** Fires with the full selected rows (so the host can show bodies + send ids). */
  onChange: (rows: Ability[]) => void
}

export function AbilityToggles({ projectRoot, selectedIds, onChange }: Props): JSX.Element {
  const [abilities, setAbilities] = useState<Ability[]>([])
  const [nonce, setNonce] = useState(0)
  const [adding, setAdding] = useState(false)
  const [name, setName] = useState('')
  const [category, setCategory] = useState<string>('build')
  const [body, setBody] = useState('')

  useEffect(() => {
    let cancelled = false
    void listAbilities(projectRoot).then((rows) => {
      if (!cancelled) setAbilities(rows)
    })
    return () => {
      cancelled = true
    }
  }, [projectRoot, nonce])

  const toggle = useCallback(
    (row: Ability) => {
      const nextIds = selectedIds.includes(row.id)
        ? selectedIds.filter((id) => id !== row.id)
        : [...selectedIds, row.id]
      onChange(abilities.filter((a) => nextIds.includes(a.id)))
    },
    [abilities, selectedIds, onChange],
  )

  async function saveNew(): Promise<void> {
    const n = name.trim()
    if (!n || !body.trim()) return
    await saveAbility({ category, name: n, body, projectRoot })
    setName('')
    setBody('')
    setAdding(false)
    setNonce((v) => v + 1)
  }

  return (
    <div className={s.wrap}>
      <div className={s.chips}>
        {abilities.map((a) => (
          <button
            key={a.id}
            type="button"
            className={s.chip}
            data-on={selectedIds.includes(a.id) ? 'true' : 'false'}
            onClick={() => toggle(a)}
            title={a.body}
          >
            {selectedIds.includes(a.id) && <Check size={11} />}
            {a.label}
            <span className={s.cat}>{a.category}</span>
          </button>
        ))}
        {!adding && (
          <button type="button" className={s.addChip} onClick={() => setAdding(true)}>
            <Plus size={11} /> Ability
          </button>
        )}
      </div>

      {adding && (
        <div className={s.form}>
          <div className={s.formRow}>
            <input
              className={s.input}
              placeholder="Ability name…"
              value={name}
              autoFocus
              onChange={(e) => setName(e.currentTarget.value)}
            />
            <select
              className={s.select}
              value={category}
              aria-label="Ability category"
              onChange={(e) => setCategory(e.currentTarget.value)}
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <textarea
            className={s.textarea}
            rows={3}
            placeholder="Approach / domain expertise (markdown; ## sections become toggles later)…"
            value={body}
            onChange={(e) => setBody(e.currentTarget.value)}
          />
          <div className={s.formActions}>
            <button
              type="button"
              className={s.iconBtn}
              onClick={() => void saveNew()}
              disabled={!name.trim() || !body.trim()}
              aria-label="Save ability"
            >
              <Check size={13} />
            </button>
            <button
              type="button"
              className={s.iconBtn}
              onClick={() => {
                setAdding(false)
                setName('')
                setBody('')
              }}
              aria-label="Cancel"
            >
              <X size={13} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
