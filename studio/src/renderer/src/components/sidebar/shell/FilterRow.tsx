import { ChevronsUp } from 'lucide-react'
import { Tooltip } from '../../ui'
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
        <Tooltip label="Clear filter" placement="bottom">
          <button
            type="button"
            className={styles.filterClear}
            onClick={onClear}
            aria-label="Clear filter"
          >
            ×
          </button>
        </Tooltip>
      )}
      {!libraryOpen && onCollapseAll && (
        <Tooltip label="Collapse all folders" placement="bottom">
          <button
            type="button"
            className={styles.collapseAll}
            onClick={onCollapseAll}
            aria-label="Collapse all folders"
          >
            <ChevronsUp size={14} />
          </button>
        </Tooltip>
      )}
    </div>
  )
}
