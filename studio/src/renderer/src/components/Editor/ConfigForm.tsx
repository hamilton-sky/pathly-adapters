export interface FrontmatterValues {
  name?: string
  description?: string
  adapters?: string[]
  tools?: string[]
  [key: string]: unknown
}

interface ConfigFormProps {
  values: FrontmatterValues
  onChange: (v: FrontmatterValues) => void
}

const KNOWN_KEYS = ['name', 'description', 'adapters', 'tools']
const ADAPTER_OPTIONS = ['claude', 'codex', 'copilot']

export function ConfigForm({ values, onChange }: ConfigFormProps): JSX.Element {
  const unknownKeys = Object.keys(values).filter((k) => !KNOWN_KEYS.includes(k))

  function set(patch: Partial<FrontmatterValues>): void {
    onChange({ ...values, ...patch })
  }

  function toggleAdapter(adapter: string, checked: boolean): void {
    const current = values.adapters ?? []
    const next = checked ? [...current, adapter] : current.filter((a) => a !== adapter)
    set({ adapters: next })
  }

  return (
    <div style={styles.form}>
      <div style={styles.row}>
        <label style={styles.label}>name</label>
        <input
          style={styles.input}
          type="text"
          value={values.name ?? ''}
          onChange={(e) => set({ name: e.target.value })}
        />
      </div>

      <div style={styles.row}>
        <label style={styles.label}>description</label>
        <input
          style={styles.input}
          type="text"
          value={values.description ?? ''}
          onChange={(e) => set({ description: e.target.value })}
        />
      </div>

      <div style={styles.row}>
        <label style={styles.label}>adapters</label>
        <div style={styles.checkboxGroup}>
          {ADAPTER_OPTIONS.map((adapter) => (
            <label key={adapter} style={styles.checkboxLabel}>
              <input
                type="checkbox"
                checked={(values.adapters ?? []).includes(adapter)}
                onChange={(e) => toggleAdapter(adapter, e.target.checked)}
                style={styles.checkbox}
              />
              {adapter}
            </label>
          ))}
        </div>
      </div>

      <div style={styles.row}>
        <label style={styles.label}>tools</label>
        <input
          style={styles.input}
          type="text"
          value={(values.tools ?? []).join(', ')}
          onChange={(e) => {
            const raw = e.target.value
            const tools = raw
              .split(',')
              .map((s) => s.trim())
              .filter(Boolean)
            set({ tools })
          }}
          placeholder="comma-separated"
        />
      </div>

      {unknownKeys.map((k) => (
        <div key={k} style={styles.row}>
          <label style={styles.label}>{k}</label>
          <span style={styles.unknownValue}>{String(values[k])}</span>
        </div>
      ))}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  form: {
    padding: '12px 16px',
    backgroundColor: '#181825',
    borderBottom: '1px solid #313244',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px'
  },
  row: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px'
  },
  label: {
    width: '100px',
    fontSize: '12px',
    color: '#a6adc8',
    fontFamily: "'Fira Mono', monospace",
    flexShrink: 0
  },
  input: {
    flex: 1,
    backgroundColor: '#1e1e2e',
    border: '1px solid #313244',
    borderRadius: '4px',
    color: '#cdd6f4',
    fontSize: '13px',
    padding: '4px 8px',
    outline: 'none'
  },
  checkboxGroup: {
    display: 'flex',
    gap: '16px'
  },
  checkboxLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    fontSize: '13px',
    color: '#cdd6f4',
    cursor: 'pointer'
  },
  checkbox: {
    accentColor: '#cba6f7'
  },
  unknownValue: {
    fontSize: '13px',
    color: '#a6adc8',
    fontFamily: "'Fira Mono', monospace"
  }
}
