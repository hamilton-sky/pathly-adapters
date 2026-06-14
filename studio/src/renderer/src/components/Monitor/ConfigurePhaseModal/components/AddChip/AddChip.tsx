import { Plus } from 'lucide-react'
import styles from './AddChip.module.css'

/** Dashed “+ add” affordance that sits at the end of a chip row. */
export function AddChip({
  onClick,
  label = 'add',
}: {
  onClick?: () => void
  label?: string
}): JSX.Element {
  return (
    <button type="button" className={styles.add} onClick={onClick} aria-label={`Add ${label}`}>
      <Plus size={13} />
      {label}
    </button>
  )
}
