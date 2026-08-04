import { useEffect, useRef, useState } from 'react'
import { apiFetch } from '../../lib/config'
import s from './ExportSkillPicker.module.css'

interface SkillRow {
  name: string
  default: boolean
  installed: boolean
}

interface Props {
  adapter: string
  onChange: (selected: Set<string>) => void
}

/**
 * Tier-2 skill picker for the export panel. Pre-checks whatever is currently installed
 * on the host, so checking a row exports it and unchecking removes it on the next Export
 * (the reconcile happens server-side via pathly-setup --repair). Reports the selected set up.
 */
export function ExportSkillPicker({ adapter, onChange }: Props): JSX.Element {
  const [skills, setSkills] = useState<SkillRow[]>([])
  const [picked, setPicked] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  // Keep the latest onChange without making it an effect dependency.
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    apiFetch(`/ops/export/skills?adapter=${encodeURIComponent(adapter)}`)
      .then((r) => r.json())
      .then((data: { skills?: SkillRow[] }) => {
        if (cancelled) return
        const rows = (data.skills ?? []).filter((sk) => !sk.default)
        const installed = new Set(
          rows.filter((sk) => sk.installed).map((sk) => sk.name),
        )
        setSkills(rows)
        setPicked(installed)
        onChangeRef.current(installed)
      })
      .catch((e) => {
        if (!cancelled) setError(String(e))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [adapter])

  function toggle(name: string): void {
    setPicked((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      onChangeRef.current(next)
      return next
    })
  }

  if (loading) return <div className={s.status}>Loading skills…</div>
  if (error) return <div className={s.status}>Couldn’t load skills: {error}</div>

  return (
    <div className={s.grid} role="group" aria-label="Skills to expose">
      {skills.map((sk) => (
        <label key={sk.name} className={s.row}>
          <input
            type="checkbox"
            checked={picked.has(sk.name)}
            onChange={() => toggle(sk.name)}
            aria-label={`Expose ${sk.name}`}
          />
          <span className={s.name}>{sk.name}</span>
          {sk.installed && <span className={s.tag}>exposed</span>}
        </label>
      ))}
    </div>
  )
}
