import styles from '../Sidebar.module.css'

interface FilterRowProps {
  filter: string
  onChange: (v: string) => void
  onClear: () => void
}

export function FilterRow({ filter, onChange, onClear }: FilterRowProps): JSX.Element {
  return (
    <div className={styles.filterRow}>
      <input
        className={styles.filterInput}
        placeholder="Filter…"
        value={filter}
        onChange={(e) => onChange(e.target.value)}
      />
      {filter && (
        <button
          type="button"
          className={styles.filterClear}
          onClick={onClear}
          title="Clear filter"
        >
          ×
        </button>
      )}
    </div>
  )
}
