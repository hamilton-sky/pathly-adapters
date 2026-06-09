import { FolderOpen } from 'lucide-react'
import styles from './EmptyState.module.css'

export function EmptyState(): JSX.Element {
  return (
    <div className={styles.wrap}>
      <FolderOpen size={32} className={styles.icon} />
      <span className={styles.title}>No projects yet</span>
      <span className={styles.sub}>Open a folder to get started</span>
    </div>
  )
}
