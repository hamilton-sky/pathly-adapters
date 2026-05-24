import styles from '../Sidebar.module.css'

interface FilterRowProps {
  libraryOpen: boolean
  filter: string
  onChange: (v: string) => void
  onClear: () => void
}

export function FilterRow({ libraryOpen, filter, onChange, onClear }: FilterRowProps): JSX.Element {
  return (
    <div className={styles.filterRow}>
      <input
        className={styles.filterInput}
        placeholder={libraryOpen ? 'Search library…' : 'Filter…'}
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
