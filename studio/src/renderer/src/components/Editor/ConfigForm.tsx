import styles from './ConfigForm.module.css'
import type { FrontmatterValues } from '../../types'

type OmitType<T> = T extends unknown ? Omit<T, 'type'> : never

interface ConfigFormProps {
  values: FrontmatterValues
  onChange: (v: FrontmatterValues) => void
  compact?: boolean
}

const KNOWN_KEYS = ['name', 'description', 'adapters', 'tools', 'model', 'category', 'type']
const ADAPTER_OPTIONS = ['claude', 'codex', 'copilot']

// Brand colours — not theme-derived, intentionally static
const ADAPTER_META: Record<string, { color: string; bg: string; border: string }> = {
  claude:  { color: '#E07535', bg: 'rgba(224,117,53,0.12)',  border: 'rgba(224,117,53,0.5)'  },
  codex:   { color: '#0EA5E9', bg: 'rgba(14,165,233,0.12)',  border: 'rgba(14,165,233,0.5)'  },
  copilot: { color: '#8888AA', bg: 'rgba(136,136,170,0.12)', border: 'rgba(136,136,170,0.5)' },
}

function chipVars(active: boolean, meta: typeof ADAPTER_META['claude']): React.CSSProperties {
  return active
    ? { '--chip-color': meta.color, '--chip-bg': meta.bg, '--chip-border': meta.border, '--chip-dot-color': meta.color } as React.CSSProperties
    : {}
}

function hasAdapters(v: FrontmatterValues): v is Extract<FrontmatterValues, { adapters?: string[] }> {
  return v.type === 'skill' || v.type === 'agent'
}

function hasTools(v: FrontmatterValues): v is Extract<FrontmatterValues, { tools?: string[] }> {
  return v.type === 'skill'
}

export function ConfigForm({ values, onChange, compact = false }: ConfigFormProps): JSX.Element {
  const unknownKeys = Object.keys(values).filter((k) => !KNOWN_KEYS.includes(k))

  function set(patch: Partial<OmitType<FrontmatterValues>>): void {
    onChange({ ...values, ...patch } as FrontmatterValues)
  }

  function toggleAdapter(adapter: string, active: boolean): void {
    if (!hasAdapters(values)) return
    const current = values.adapters ?? []
    set({ adapters: active ? [...current, adapter] : current.filter((a) => a !== adapter) })
  }

  const adapterChipsEl = hasAdapters(values) ? (
    <div className={styles.adapterChips}>
      {ADAPTER_OPTIONS.map((adapter) => {
        const meta = ADAPTER_META[adapter]
        const active = (values.adapters ?? []).includes(adapter)
        return (
          <div
            key={adapter}
            className={styles.chip}
            style={chipVars(active, meta)}
            onClick={() => toggleAdapter(adapter, !active)}
            title={active ? `Remove ${adapter}` : `Add ${adapter}`}
          >
            <span className={styles.chipDot} />
            {adapter}
          </div>
        )
      })}
    </div>
  ) : null

  if (compact) {
    return (
      <div className={styles.card}>
        <div className={styles.cardBodyCompact}>
          <span className={styles.nameValue}>{values.name || '—'}</span>
          {adapterChipsEl}
        </div>
      </div>
    )
  }

  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>Configuration</div>
      <div className={styles.cardBody}>
        <div className={styles.row}>
          <span className={styles.label}>Name</span>
          <input
            className={styles.input}
            type="text"
            value={values.name ?? ''}
            onChange={(e) => set({ name: e.target.value })}
            placeholder="skill-name"
          />
        </div>

        {'description' in values && (
          <div className={styles.row}>
            <span className={styles.label}>Description</span>
            <input
              className={styles.input}
              type="text"
              value={values.description ?? ''}
              onChange={(e) => set({ description: e.target.value })}
              placeholder="What does this skill do?"
            />
          </div>
        )}

        {hasAdapters(values) && (
          <div className={styles.row}>
            <span className={styles.label}>Adapters</span>
            {adapterChipsEl}
          </div>
        )}

        {hasTools(values) && (
          <div className={styles.row}>
            <span className={styles.label}>Tools</span>
            <input
              className={styles.input}
              type="text"
              value={(values.tools ?? []).join(', ')}
              onChange={(e) => {
                const tools = e.target.value.split(',').map((s) => s.trim()).filter(Boolean)
                set({ tools })
              }}
              placeholder="Bash, Read, Glob, …"
            />
          </div>
        )}

        {unknownKeys.map((k) => (
          <div key={k} className={styles.row}>
            <span className={styles.label}>{k}</span>
            <span className={styles.unknownValue}>{String((values as Record<string, unknown>)[k])}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
