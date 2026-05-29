import styles from '../Sidebar.module.css'

interface TabBarProps {
  libraryOpen: boolean
  onSwitch: (tab: 'library' | 'workspace') => void
}

export function TabBar({ libraryOpen, onSwitch }: TabBarProps): JSX.Element {
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
    </div>
  )
}
