import { PanelLeft } from 'lucide-react'
import styles from '../Sidebar.module.css'

interface TabBarProps {
  libraryOpen: boolean
  onSwitch: (tab: 'library' | 'workspace') => void
  onCollapse: () => void
}

export function TabBar({ libraryOpen, onSwitch, onCollapse }: TabBarProps): JSX.Element {
  return (
    <div className={styles.tabBar} role="tablist" aria-label="Sidebar view">
      <button
        type="button"
        role="tab"
        aria-selected={!libraryOpen}
        className={`${styles.tab} ${!libraryOpen ? styles.tabActive : ''}`}
        onClick={() => onSwitch('workspace')}
      >
        WORKSPACE
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={libraryOpen}
        className={`${styles.tab} ${libraryOpen ? styles.tabActive : ''}`}
        onClick={() => onSwitch('library')}
      >
        LIBRARY
      </button>
      <button
        type="button"
        className={styles.sbCollapse}
        title="Collapse sidebar"
        aria-expanded="true"
        aria-label="Collapse sidebar"
        onClick={onCollapse}
      >
        <PanelLeft size={15} />
      </button>
    </div>
  )
}
