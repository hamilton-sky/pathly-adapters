import React, { useEffect } from 'react'
import { GitBranch, Folder, Globe } from 'lucide-react'
import type { BoardScope } from '../types'
import { CommsPanel } from '../CommsPanel/CommsPanel/CommsPanel'
import { useProjectStore } from '../../../store/projectStore'
import { useUiStore } from '../../../store/uiStore'
import { useCommsStore } from '../../../store/commsStore'
import s from './PopoutBoard.module.css'

const SCOPE_ICONS: Record<BoardScope, React.ReactNode> = {
  feature: <GitBranch size={15} />,
  project: <Folder size={15} />,
  global: <Globe size={15} />,
}

interface PopoutBoardProps {
  scope: BoardScope
  /** Feature id for a feature board; the active main-feature for project/global. */
  feature: string
  project: string
  name: string
}

// A single board torn off into its own OS window. It talks to the same local
// Pathly server (127.0.0.1:8765) as the main window — each window opens its own
// HTTP + SSE connection, so this stays fully live. projectStore does NOT persist
// projectPath, so it is seeded here from the query param the opener passed.
export function PopoutBoard({ scope, feature, project, name }: PopoutBoardProps): JSX.Element {
  const theme = useUiStore((st) => st.theme)
  const setProjectPath = useProjectStore((st) => st.setProjectPath)
  const loadFeatures = useCommsStore((st) => st.loadFeatures)

  // tokens.css resolves every color from [data-theme]; the theme name rehydrates
  // from shared localStorage, so applying the attribute is all this window needs.
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  useEffect(() => {
    if (!project) return
    setProjectPath(project)
    void loadFeatures(project)
  }, [project, setProjectPath, loadFeatures])

  return (
    <div className={s.popout}>
      <div className={s.head}>
        <span className={s.icon}>{SCOPE_ICONS[scope]}</span>
        <span className={s.name} title={name}>{name}</span>
      </div>
      <CommsPanel scope={scope} mainFeature={feature} />
    </div>
  )
}
