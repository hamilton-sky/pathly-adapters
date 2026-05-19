import { ChevronRight, ChevronDown, Folder } from 'lucide-react'
import styles from './Sidebar.module.css'

interface Props {
  name: string
  open: boolean
  onToggle: () => void
  depth?: number
}

export function SubdirRow({ name, open, onToggle }: Props): JSX.Element {
  return (
    <button className={styles.subdirHeader} onClick={onToggle}>
      <span className={styles.chevron}>
        {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
      </span>
      <Folder size={13} style={{ color: 'var(--accent)', flexShrink: 0 }} />
      <span style={{ flex: 1, textAlign: 'left' }}>{name}/</span>
    </button>
  )
}
