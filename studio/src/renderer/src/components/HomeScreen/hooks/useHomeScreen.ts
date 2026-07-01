import { useState } from 'react'
import { useStore } from '../../../store'
import { pickFolder, openWindow, scaffoldPathlyWorkspace } from '../../../services/pathlyApi'
import type { ProjectEntry } from '../../../types'

type Tab = 'projects' | 'getting-started' | 'settings'
type ViewMode = 'grid' | 'list'

export function useHomeScreen() {
  const { addProject, setProjectPath, updateProject, setActiveTopic } = useStore()

  const [activeTab, setActiveTab] = useState<Tab>(
    (localStorage.getItem('pathly-home-tab') as Tab) ?? 'projects'
  )
  const [viewMode, setViewMode] = useState<ViewMode>(
    (localStorage.getItem('pathly-home-view') as ViewMode) ?? 'grid'
  )
  const [hideDone, setHideDone] = useState(true)
  const [visibleCount, setVisibleCount] = useState(6)

  function handleTab(tab: Tab): void {
    localStorage.setItem('pathly-home-tab', tab)
    setActiveTab(tab)
  }

  function handleViewMode(mode: ViewMode): void {
    localStorage.setItem('pathly-home-view', mode)
    setViewMode(mode)
  }

  async function handleOpenFolder(): Promise<void> {
    const folderPath = await pickFolder()
    if (!folderPath) return
    await scaffoldPathlyWorkspace(folderPath)
    const name = folderPath.split(/[/\\]/).filter(Boolean).pop() ?? folderPath
    addProject({ path: folderPath, name, lastOpened: Date.now() })
  }

  function handleOpen(project: ProjectEntry, topicName?: string, evt?: React.MouseEvent): void {
    if (evt?.metaKey || evt?.ctrlKey) {
      openWindow(project.path)
    } else {
      updateProject(project.path, { lastOpened: Date.now() })
      if (topicName) setActiveTopic(topicName)
      setProjectPath(project.path)
    }
  }

  return {
    activeTab, handleTab,
    viewMode, handleViewMode,
    hideDone, setHideDone,
    visibleCount, setVisibleCount,
    handleOpenFolder, handleOpen,
  }
}
