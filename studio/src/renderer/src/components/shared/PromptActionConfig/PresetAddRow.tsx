// PresetAddRow — the "＋ Save current as prompt" affordance in every prompt config.
// Collapsed to a single button; expands to a name field + confirm/cancel. On save it
// hands the entered name to the host, which persists the CURRENT prompt text under it.

import { useState } from 'react'
import { Plus, Check, X } from 'lucide-react'
import s from './PresetAddRow.module.css'

interface Props {
  /** Persist the current prompt text under `name`. */
  onAdd: (name: string) => void | Promise<void>
}

export function PresetAddRow({ onAdd }: Props): JSX.Element {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)

  async function save(): Promise<void> {
    const n = name.trim()
    if (!n || busy) return
    setBusy(true)
    try {
      await onAdd(n)
      setName('')
      setOpen(false)
    } finally {
      setBusy(false)
    }
  }

  function cancel(): void {
    setOpen(false)
    setName('')
  }

  if (!open) {
    return (
      <button type="button" className={s.addBtn} onClick={() => setOpen(true)}>
        <Plus size={12} />
        Save current as prompt
      </button>
    )
  }

  return (
    <div className={s.row}>
      <input
        className={s.input}
        value={name}
        placeholder="Prompt name…"
        autoFocus
        onChange={(e) => setName(e.currentTarget.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault()
            void save()
          }
          if (e.key === 'Escape') cancel()
        }}
      />
      <button
        type="button"
        className={s.iconBtn}
        onClick={() => void save()}
        disabled={busy || !name.trim()}
        aria-label="Save prompt"
      >
        <Check size={13} />
      </button>
      <button type="button" className={s.iconBtn} onClick={cancel} aria-label="Cancel">
        <X size={13} />
      </button>
    </div>
  )
}
