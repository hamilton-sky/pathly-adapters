import { useState } from 'react'
import { X, Check } from 'lucide-react'
import { saveUserPrompt } from '../../../services/promptLibrary'
import { FIXED_CATEGORIES } from '../../shared/LibraryCatalog/utils'
import s from './SystemPromptModal.module.css'

// The Library's create surface for a system-prompt (a prompt_library preset row). Name +
// category + body → POST /skills/prompts. Once saved it appears in the Library's System group
// AND the Sections modal's System tab (both read the same table). Creation lives ONLY here.
const CATEGORIES = FIXED_CATEGORIES.system

interface Props {
  initialName?: string
  projectRoot: string
  /** Resolve the host's create Promise so the catalog re-fetches. Called on save AND cancel. */
  onClose: () => void
}

export function SystemPromptModal({ initialName = '', projectRoot, onClose }: Props): JSX.Element {
  const [name, setName] = useState(initialName)
  const [category, setCategory] = useState<string>('system')
  const [body, setBody] = useState('')
  const [saving, setSaving] = useState(false)

  const canSave = name.trim().length > 0 && body.trim().length > 0 && !saving

  async function save(): Promise<void> {
    if (!canSave) return
    setSaving(true)
    await saveUserPrompt({
      kind: 'preset',
      category: category.trim() || 'system',
      name: name.trim(),
      body,
      projectRoot,
    })
    setSaving(false)
    onClose()
  }

  return (
    <div className={s.backdrop} onClick={onClose}>
      <div className={s.modal} role="dialog" aria-modal="true" aria-label="New system prompt" onClick={(e) => e.stopPropagation()}>
        <div className={s.header}>
          <span className={s.title}>New system prompt</span>
          <button type="button" className={s.closeBtn} onClick={onClose} aria-label="Cancel">
            <X size={15} />
          </button>
        </div>

        <div className={s.body}>
          <div className={s.row}>
            <input
              className={s.input}
              placeholder="Name…"
              value={name}
              autoFocus
              onChange={(e) => setName(e.currentTarget.value)}
            />
            <select className={s.select} value={category} aria-label="Category" onChange={(e) => setCategory(e.currentTarget.value)}>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <textarea
            className={s.textarea}
            rows={10}
            placeholder="System-prompt body (markdown)… this is what gets folded into a run when you add it in Sections."
            value={body}
            onChange={(e) => setBody(e.currentTarget.value)}
          />
        </div>

        <div className={s.footer}>
          <button type="button" className={s.cancelBtn} onClick={onClose}>Cancel</button>
          <button type="button" className={s.saveBtn} disabled={!canSave} onClick={() => void save()}>
            <Check size={14} /> {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
