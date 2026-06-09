import { LayoutGrid, List } from 'lucide-react'
import { SectionLabel } from '../SectionLabel/SectionLabel'
import styles from './ProjectsToolbar.module.css'

interface ProjectsToolbarProps {
  viewMode: 'grid' | 'list'
  hideDone: boolean
  onViewModeChange: (mode: 'grid' | 'list') => void
  onToggleHideDone: () => void
  onNewProject: () => void
}

export function ProjectsToolbar({ viewMode, hideDone, onViewModeChange, onToggleHideDone, onNewProject }: ProjectsToolbarProps): JSX.Element {
  return (
    <div className={styles.toolbar}>
      <SectionLabel label="Recent Projects" animDelay={60} />

      <div className={styles.controls}>
        <button
          type="button"
          data-testid="homescreen-new-project-btn"
          className={styles.newBtn}
          onClick={onNewProject}
          title="Open project folder"
        >
          + New project
        </button>

        <div className={styles.viewToggle}>
          <button
            type="button"
            data-testid="homescreen-view-grid-btn"
            className={`${styles.viewBtn} ${viewMode === 'grid' ? styles.active : ''}`}
            onClick={() => onViewModeChange('grid')}
            title="Grid view"
            aria-label="Grid view"
            aria-pressed={viewMode === 'grid'}
          >
            <LayoutGrid size={15} />
          </button>
          <button
            type="button"
            data-testid="homescreen-view-list-btn"
            className={`${styles.viewBtn} ${viewMode === 'list' ? styles.active : ''}`}
            onClick={() => onViewModeChange('list')}
            title="List view"
            aria-label="List view"
            aria-pressed={viewMode === 'list'}
          >
            <List size={15} />
          </button>
        </div>

        <button
          type="button"
          data-testid="home-toggle-done-btn"
          className={`${styles.toggleBtn} ${hideDone ? styles.toggleActive : ''}`}
          onClick={onToggleHideDone}
        >
          {hideDone ? 'Show all' : 'Hide done'}
        </button>
      </div>
    </div>
  )
}
