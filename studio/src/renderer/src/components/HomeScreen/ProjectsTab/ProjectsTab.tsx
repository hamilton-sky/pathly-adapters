import type { ProjectEntry } from '../../../types'
import type { ProjectPlans } from '../types'
import { ProjectsToolbar } from '../ProjectsToolbar/ProjectsToolbar'
import { ProjectGrid } from '../ProjectGrid/ProjectGrid'
import { EmptyState } from '../EmptyState/EmptyState'
import styles from './ProjectsTab.module.css'

interface ProjectsTabProps {
  projects: ProjectEntry[]
  projectPlans: ProjectPlans
  viewMode: 'grid' | 'list'
  hideDone: boolean
  visibleCount: number
  onViewModeChange: (mode: 'grid' | 'list') => void
  onToggleHideDone: () => void
  onNewProject: () => void
  onLoadMore: () => void
  onOpen: (project: ProjectEntry, topicName?: string, evt?: React.MouseEvent) => void
  onPin: (path: string) => void
  onRemove: (path: string) => void
}

export function ProjectsTab({
  projects,
  projectPlans,
  viewMode,
  hideDone,
  visibleCount,
  onViewModeChange,
  onToggleHideDone,
  onNewProject,
  onLoadMore,
  onOpen,
  onPin,
  onRemove,
}: ProjectsTabProps): JSX.Element {
  const sorted = [...projects]
    .filter((p, i, arr) => arr.findIndex((q) => q.path === p.path) === i)
    .sort((a, b) => b.lastOpened - a.lastOpened)

  const pinnedProjects = sorted.filter((p) => p.pinned)
  const unpinnedProjects = sorted.filter((p) => !p.pinned)

  return (
    <div className={styles.wrap}>
      <h1 className={styles.title}>Pathly Studio</h1>
      <p className={styles.subtitle}>Welcome back. Pick up where you left off.</p>

      <ProjectsToolbar
        viewMode={viewMode}
        hideDone={hideDone}
        onViewModeChange={onViewModeChange}
        onToggleHideDone={onToggleHideDone}
        onNewProject={onNewProject}
      />

      {sorted.length === 0 ? (
        <EmptyState />
      ) : (
        <ProjectGrid
          pinnedProjects={pinnedProjects}
          unpinnedProjects={unpinnedProjects}
          viewMode={viewMode}
          visibleCount={visibleCount}
          projectPlans={projectPlans}
          hideDone={hideDone}
          onLoadMore={onLoadMore}
          onOpen={onOpen}
          onPin={onPin}
          onRemove={onRemove}
        />
      )}
    </div>
  )
}
