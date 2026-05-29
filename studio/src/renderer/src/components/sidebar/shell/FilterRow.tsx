import { ChevronsUp } from 'lucide-react'
import styles from '../Sidebar.module.css'

interface FilterRowProps {
  libraryOpen: boolean
  filter: string
  onChange: (v: string) => void
  onClear: () => void
  onCollapseAll?: () => void
}

export function FilterRow({ libraryOpen, filter, onChange, onClear, onCollapseAll }: FilterRowProps): JSX.Element {
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
      {!libraryOpen && onCollapseAll && (
        <button
          type="button"
          className={styles.collapseAll}
          onClick={onCollapseAll}
          title="Collapse all folders"
          aria-label="Collapse all folders"
        >
          <ChevronsUp size={14} />
        </button>
      )}
    </div>
  )
}
