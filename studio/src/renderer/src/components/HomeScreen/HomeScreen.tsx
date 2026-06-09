import { useStore } from '../../store'
import { useHomeScreen } from './hooks/useHomeScreen'
import { useProjectPlans } from './hooks/useProjectPlans'
import { AppHeader } from './AppHeader/AppHeader'
import { ProjectsTab } from './ProjectsTab/ProjectsTab'
import { Settings } from '../Settings'
import { GettingStarted } from '../GettingStarted/GettingStarted'
import styles from './HomeScreen.module.css'

export function HomeScreen(): JSX.Element {
  const { projects, removeProject, updateProject } = useStore()
  const projectPlans = useProjectPlans()
  const {
    activeTab, handleTab,
    viewMode, handleViewMode,
    hideDone, setHideDone,
    visibleCount, setVisibleCount,
    handleOpenFolder, handleOpen,
  } = useHomeScreen()

  return (
    <div data-testid="home-screen" className={styles.screen}>
      <AppHeader activeTab={activeTab} onTabChange={handleTab} />

      {activeTab === 'settings' && (
        <div className={styles.settingsWrap}><Settings /></div>
      )}

      {activeTab === 'getting-started' && (
        <GettingStarted onGoToProjects={() => handleTab('projects')} />
      )}

      {activeTab === 'projects' && (
        <ProjectsTab
          projects={projects}
          projectPlans={projectPlans}
          viewMode={viewMode}
          hideDone={hideDone}
          visibleCount={visibleCount}
          onViewModeChange={handleViewMode}
          onToggleHideDone={() => setHideDone((v) => !v)}
          onNewProject={handleOpenFolder}
          onLoadMore={() => setVisibleCount((n) => n + 6)}
          onOpen={handleOpen}
          onPin={(path) => updateProject(path, { pinned: !projects.find((p) => p.path === path)?.pinned })}
          onRemove={removeProject}
        />
      )}
    </div>
  )
}
