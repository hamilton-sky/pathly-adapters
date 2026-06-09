import { SectionLabel } from '../SectionLabel/SectionLabel'
import { ProjectCard } from '../ProjectCard/ProjectCard'
import type { ProjectEntry } from '../../../types'
import type { ProjectPlans } from '../types'
import styles from './ProjectGrid.module.css'

interface ProjectGridProps {
  pinnedProjects: ProjectEntry[]
  unpinnedProjects: ProjectEntry[]
  viewMode: 'grid' | 'list'
  visibleCount: number
  projectPlans: ProjectPlans
  hideDone: boolean
  onLoadMore: () => void
  onOpen: (project: ProjectEntry, topicName?: string, evt?: React.MouseEvent) => void
  onPin: (path: string) => void
  onRemove: (path: string) => void
}

export function ProjectGrid({
  pinnedProjects,
  unpinnedProjects,
  viewMode,
  visibleCount,
  projectPlans,
  hideDone,
  onLoadMore,
  onOpen,
  onPin,
  onRemove,
}: ProjectGridProps): JSX.Element {
  const visibleUnpinned = unpinnedProjects.slice(0, Math.max(0, visibleCount - pinnedProjects.length))
  const hiddenCount = unpinnedProjects.length - visibleUnpinned.length
  const displayUnpinned = pinnedProjects.length > 0 ? visibleUnpinned : unpinnedProjects.slice(0, visibleCount)

  function renderCard(project: ProjectEntry, idx: number): JSX.Element {
    const allPlans = projectPlans[project.path] ?? []
    const plans = hideDone ? allPlans.filter((p) => p.state.toUpperCase() !== 'DONE') : allPlans
    return (
      <ProjectCard
        key={project.path}
        project={project}
        plans={plans}
        allPlans={allPlans}
        index={idx}
        onOpen={(topicName, evt) => onOpen(project, topicName, evt)}
        onPin={() => onPin(project.path)}
        onRemove={() => onRemove(project.path)}
      />
    )
  }

  return (
    <>
      <div className={viewMode === 'grid' ? styles.grid : styles.list}>
        {pinnedProjects.length > 0 && (
          <>
            <div className={styles.fullRow}>
              <SectionLabel label="Pinned" animDelay={0} />
            </div>
            {pinnedProjects.map((project, idx) => renderCard(project, idx))}
            <div className={styles.separator} />
            <div className={styles.fullRow}>
              <SectionLabel label="Recent" animDelay={0} />
            </div>
          </>
        )}
        {displayUnpinned.map((project, idx) => renderCard(project, pinnedProjects.length + idx))}
      </div>

      {hiddenCount > 0 && (
        <button
          type="button"
          data-testid="home-show-more-btn"
          className={styles.showMore}
          onClick={onLoadMore}
        >
          Show {hiddenCount} more
        </button>
      )}
    </>
  )
}
