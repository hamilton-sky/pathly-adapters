import { ChevronRight, ChevronDown } from 'lucide-react'
import styles from './Sidebar.module.css'

interface Props {
  label: string
  open: boolean
  onToggle: () => void
  actions?: React.ReactNode
  sub?: string
}

export function SectionHeader({ label, open, onToggle, actions, sub }: Props): JSX.Element {
  return (
    <div className={styles.sectionRow}>
      <button className={styles.sectionToggle} onClick={onToggle}>
        <span className={styles.chevron}>
          {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
        </span>
        {label}
        {sub && <span className={styles.sectionSub}>{sub}</span>}
      </button>
      {actions && <div className={styles.sectionActions}>{actions}</div>}
    </div>
  )
}
