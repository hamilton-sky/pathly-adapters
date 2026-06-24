import React from 'react'
import { GitBranch, Folder, Globe, X } from 'lucide-react'
import type { BoardScope, Preset, Direction, SectionDef } from '../types'
import { SCOPES } from '../constants'
import { CommsPanel } from '../CommsPanel/CommsPanel'
import { Tooltip } from '../../ui'
import s from './BoardSection.module.css'

export interface BoardSectionProps {
  section: SectionDef
  mainFeature: string
  preset: Preset
  direction: Direction
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
  if (props.preset === 'board' && props.direction === 'row') return `${BOARD_WEIGHT[props.section.scope]} 1 0`
  return '1 1 0'
}

function getBoardName(section: SectionDef): string {
  if (section.scope === 'feature') return section.featureId
  if (section.scope === 'project') return 'pathly-adapters'
  return 'all projects · all features'
}

export function BoardSection(props: BoardSectionProps) {
  const { section, mainFeature, onClose } = props
  const sc = SCOPES[section.scope]
  const flexValue = getSectionFlex(props)
  const panelFeature = section.scope === 'feature' ? section.featureId : mainFeature

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
        <Tooltip label={getBoardName(section)} placement="bottom">
          <span className={s.bsName}>{getBoardName(section)}</span>
        </Tooltip>
        <div className={s.bsHeadActs}>
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
