import styles from '../Sidebar.module.css'

interface SidebarHeaderProps {
  context: 'workspace' | 'library'
}

export function SidebarHeader({ context }: SidebarHeaderProps): JSX.Element {
  const label = context === 'library' ? 'Library' : 'Workspace'
  return <div className={styles.sidebarHeader}>{label}</div>
}
