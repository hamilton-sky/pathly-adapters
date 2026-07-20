import { useState } from 'react'
import { X, Check } from 'lucide-react'
import { saveAbility } from '../../../services/abilities'
import { FIXED_CATEGORIES } from '../../shared/LibraryCatalog/utils'
import s from './AbilityCreateModal.module.css'

// The Library's create surface for a layer-3 ability (a markdown FILE). Category + name + scope
// + body → POST /skills/abilities. Once saved it appears in the Library's Abilities group AND
// the Sections modal's Abilities tab (both read the merged ability files). Creation lives ONLY here.
const CATEGORIES = FIXED_CATEGORIES.ability

interface Props {
  initialName?: string
  /** Pre-select the category (e.g. clicking "+ New" inside the BUILD subfolder). */
  initialCategory?: string
  projectRoot: string
  /** Resolve the host's create Promise so the catalog re-fetches. Called on save AND cancel. */
  onClose: () => void
}

export function AbilityCreateModal({ initialName = '', initialCategory, projectRoot, onClose }: Props): JSX.Element {
  const [name, setName] = useState(initialName)
  const [category, setCategory] = useState<string>(initialCategory && CATEGORIES.includes(initialCategory) ? initialCategory : 'build')
  const [scope, setScope] = useState<'project' | 'global'>('project')
  const [body, setBody] = useState('')
  const [saving, setSaving] = useState(false)

  const canSave = name.trim().length > 0 && body.trim().length > 0 && !saving

  async function save(): Promise<void> {
    if (!canSave) return
    setSaving(true)
    await saveAbility({ category, name: name.trim(), body, scope, projectRoot })
    setSaving(false)
    onClose()
  }

  return (
    <div className={s.backdrop} onClick={onClose}>
      <div className={s.modal} role="dialog" aria-modal="true" aria-label="New ability" onClick={(e) => e.stopPropagation()}>
        <div className={s.header}>
          <span className={s.title}>New ability</span>
          <button type="button" className={s.closeBtn} onClick={onClose} aria-label="Cancel">
            <X size={15} />
          </button>
        </div>

        <div className={s.body}>
          <div className={s.row}>
            <input
              className={s.input}
              placeholder="Name… (e.g. react-web)"
              value={name}
              autoFocus
              onChange={(e) => setName(e.currentTarget.value)}
            />
            <select className={s.select} value={category} aria-label="Category" onChange={(e) => setCategory(e.currentTarget.value)}>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            <select className={s.select} value={scope} aria-label="Scope" onChange={(e) => setScope(e.currentTarget.value as 'project' | 'global')}>
              <option value="project">Project</option>
              <option value="global">Global</option>
            </select>
          </div>
          <textarea
            className={s.textarea}
            rows={10}
            placeholder="Approach / domain pack (markdown; ## sections are its structure)… this is folded into a run when you add it in Sections."
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
