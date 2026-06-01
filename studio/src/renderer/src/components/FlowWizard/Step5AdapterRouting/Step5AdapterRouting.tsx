import styles from './Step5AdapterRouting.module.css'

const KNOWN_ADAPTERS = ['claude', 'codex', 'copilot'] as const

interface AdapterRowProps {
  label: string
  isDefault?: boolean
  currentValue: string
  resolvedValue: string
  onChange: (value: string) => void
}

function AdapterRow({ label, isDefault, currentValue, resolvedValue, onChange }: AdapterRowProps): JSX.Element {
  return (
    <div className={styles.row}>
      <span className={styles.name}>{label}</span>
      <select
        className={styles.select}
        value={currentValue}
        onChange={(e) => onChange(e.target.value)}
        aria-label={`Adapter for ${label}`}
      >
        {!isDefault && <option value="">— (use default)</option>}
        {KNOWN_ADAPTERS.map((a) => (
          <option key={a} value={a}>{a}</option>
        ))}
      </select>
      <span className={styles.chip} data-adapter={resolvedValue}>{resolvedValue}</span>
    </div>
  )
}

interface Props {
  nonTerminalStates: string[]
  adapterMap: Record<string, string>
  onUpdateAdapter: (key: string, value: string) => void
  onReset: () => void
}

export function Step5AdapterRouting({ nonTerminalStates, adapterMap, onUpdateAdapter, onReset }: Props): JSX.Element {
  const defaultAdapter = adapterMap['default'] || 'claude'

  return (
    <div className={styles.root}>
      <p className={styles.title}>Adapter Routing</p>
      <p className={styles.sub}>
        Choose which CLI adapter handles each pipeline stage. The default applies to any stage not listed.
      </p>

      <AdapterRow
        label="default"
        isDefault
        currentValue={defaultAdapter}
        resolvedValue={defaultAdapter}
        onChange={(v) => onUpdateAdapter('default', v)}
      />

      {nonTerminalStates.map((state) => {
        const override = adapterMap[state] || ''
        const resolved = override || defaultAdapter
        return (
          <AdapterRow
            key={state}
            label={state}
            currentValue={override}
            resolvedValue={resolved}
            onChange={(v) => onUpdateAdapter(state, v)}
          />
        )
      })}

      <div className={styles.resetRow}>
        <button type="button" className={styles.resetBtn} onClick={onReset}>
          Reset to defaults
        </button>
      </div>
    </div>
  )
}
