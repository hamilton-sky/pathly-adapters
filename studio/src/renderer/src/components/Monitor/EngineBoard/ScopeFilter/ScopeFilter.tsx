import s from './ScopeFilter.module.css'

interface Props {
  /** Distinct scopes present (feature slugs + '(project)'). */
  scopes: string[]
  value: string | null
  onChange: (scope: string | null) => void
}

// A compact filter to narrow the board to one scope — a feature slug, or the '(project)' bucket of
// editor/AI one-shots. Only rendered when there's more than one scope to choose between (otherwise
// the category + adapter filters already cover it).
export function ScopeFilter({ scopes, value, onChange }: Props): JSX.Element | null {
  if (scopes.length < 2) return null
  return (
    <div className={s.bar}>
      <span className={s.label}>Scope</span>
      <button
        type="button"
        className={s.chip}
        {...(value === null ? { 'data-active': '' } : {})}
        onClick={() => onChange(null)}
      >
        All
      </button>
      {scopes.map((sc) => (
        <button
          key={sc}
          type="button"
          className={s.chip}
          title={sc}
          {...(value === sc ? { 'data-active': '' } : {})}
          onClick={() => onChange(value === sc ? null : sc)}
        >
          {sc === '(project)' ? 'Project' : sc}
        </button>
      ))}
    </div>
  )
}
