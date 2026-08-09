import { useState } from 'react'
import { Plus } from 'lucide-react'
import s from './AddRoleRow.module.css'

interface Props {
  /** Reveal an override row for an arbitrary role key. */
  onAdd: (role: string) => void
  /** Role keys already shown — used to reject duplicates. */
  existing: Set<string>
}

// "+ Add override" — a free-text escape hatch so a model policy can target ANY role key (a custom
// agent not yet in the registry, a one-off identity). The resolver keys by arbitrary string, so
// whatever is typed here Just Works at spawn time; the revealed row persists once a company is
// picked.
export function AddRoleRow({ onAdd, existing }: Props): JSX.Element {
  const [value, setValue] = useState('')
  const trimmed = value.trim()
  const dup = trimmed !== '' && existing.has(trimmed)

  function commit(): void {
    if (!trimmed || dup) return
    onAdd(trimmed)
    setValue('')
  }

  return (
    <div className={s.row}>
      <input
        className={s.input}
        type="text"
        value={value}
        placeholder="Add override for a custom role…"
        aria-label="Custom role name"
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') commit()
        }}
      />
      <button
        type="button"
        className={s.addBtn}
        onClick={commit}
        disabled={!trimmed || dup}
        aria-label="Add override"
      >
        <Plus size={13} aria-hidden="true" /> Add
      </button>
    </div>
  )
}
