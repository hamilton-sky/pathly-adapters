import { useState, useRef, useEffect } from 'react'
import { Plus } from 'lucide-react'
import type { CatalogItem } from '../hooks/usePhaseModalCatalog'
import styles from './CatalogDropdown.module.css'

interface Props {
  catalog: CatalogItem[]
  isExcluded: (item: CatalogItem) => boolean
  onSelect: (item: CatalogItem) => void
  color: 'agent' | 'skill'
}

export function CatalogDropdown({ catalog, isExcluded, onSelect, color }: Props): JSX.Element {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onMouseDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onMouseDown)
    return () => document.removeEventListener('mousedown', onMouseDown)
  }, [open])

  const available = catalog.filter((item) => !isExcluded(item))

  return (
    <div className={styles.root} ref={ref}>
      <button
        type="button"
        className={styles.trigger}
        onClick={() => setOpen((o) => !o)}
        aria-label="Select from catalog"
        {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
      >
        <Plus size={12} />
      </button>
      {open && (
        <div className={styles.dropdown} role="listbox" aria-label="Catalog">
          {available.length === 0 ? (
            <span className={styles.empty}>All items shown</span>
          ) : (
            available.map((item) => (
              <button
                key={item.name}
                type="button"
                role="option"
                className={styles.item}
                data-color={color}
                onClick={() => { onSelect(item); setOpen(false) }}
              >
                {item.name}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}
