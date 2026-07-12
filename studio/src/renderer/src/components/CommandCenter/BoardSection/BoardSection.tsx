import React from 'react'
import { GitBranch, Folder, Globe, X, ExternalLink } from 'lucide-react'
import type { BoardScope, Preset, SectionDef } from '../types'
import { SCOPES } from '../constants'
import { CommsPanel } from '../CommsPanel/CommsPanel/CommsPanel'
import { useProjectStore } from '../../../store/projectStore'
import { Tooltip } from '../../ui'
import s from './BoardSection.module.css'

export interface BoardSectionProps {
  section: SectionDef
  mainFeature: string
  preset: Preset
  size?: number
  onClose: () => void
}

const SCOPE_ICONS: Record<BoardScope, React.ReactNode> = {
  feature: <GitBranch size={15} />,
  project: <Folder size={15} />,
  global:  <Globe size={15} />,
}

const BOARD_WEIGHT: Record<BoardScope, number> = { feature: 50, project: 30, global: 20 }

function getSectionFlex(props: BoardSectionProps): string {
  if (props.size) return `0 0 ${props.size}px`
  if (props.preset === 'board') return `${BOARD_WEIGHT[props.section.scope]} 1 0`
  return '1 1 0'
}

function getBoardName(section: SectionDef, projectName: string): string {
  if (section.scope === 'feature') return section.featureId
  if (section.scope === 'project') return projectName
  return 'all projects · all features'
}

export function BoardSection(props: BoardSectionProps) {
  const { section, mainFeature, onClose } = props
  const projectPath = useProjectStore((st) => st.projectPath)
  const projects = useProjectStore((st) => st.projects)
  const sc = SCOPES[section.scope]
  const flexValue = getSectionFlex(props)
  const panelFeature = section.scope === 'feature' ? section.featureId : mainFeature
  // Resolve the project's display name the same way the topbar ProjectSelector does,
  // so the PROJECT board header tracks the active project instead of a hardcoded name.
  const projectName =
    projects.find((p) => p.path === projectPath)?.name
    ?? (projectPath.split(/[/\\]/).filter(Boolean).pop() || 'project')
  const boardName = getBoardName(section, projectName)

  // Tear this board off into its own window: open the pop-out (it reconnects to
  // the same local Pathly server independently, so it stays live), then hide the
  // section here so the board lives in exactly one place — moved, not duplicated.
  // If the pop-out fails, keep the section visible.
  const handlePopout = (): void => {
    void window.pathly.board
      .popout({
        scope: section.scope,
        feature: panelFeature,
        project: projectPath,
        name: `${sc.title} · ${boardName}`,
      })
      .then(() => onClose())
      .catch(() => { /* pop-out failed — leave the section in place */ })
  }

  return (
    <div
      className={s.board}
      data-board={section.scope}
      style={{ '--section-flex': flexValue } as React.CSSProperties}
    >
      <div className={s.bsHead}>
        <span className={s.bsIcon}>{SCOPE_ICONS[section.scope]}</span>
        <span className={s.bsScope}>{sc.title}</span>
        <span className={s.bsSep}>:</span>
        <Tooltip label={boardName} placement="bottom">
          <span className={s.bsName}>{boardName}</span>
        </Tooltip>
        <div className={s.bsHeadActs}>
          <button
            type="button"
            className={s.bsIconbtn}
            title="Open board in a new window"
            aria-label="Open board in a new window"
            onClick={handlePopout}
          >
            <ExternalLink size={14} />
          </button>
          <button
            type="button"
            className={`${s.bsIconbtn} ${s.close}`}
            title="Hide section"
            aria-label="Hide section"
            onClick={onClose}
          >
            <X size={15} />
          </button>
        </div>
      </div>
      <CommsPanel scope={section.scope} mainFeature={panelFeature} />
    </div>
  )
}
