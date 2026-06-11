import React from 'react'
import { GitBranch, Folder, Globe, Plus, X } from 'lucide-react'
import type { BoardScope, Preset, Direction } from './types'
import { SCOPES } from './constants'
import { CommsPanel } from '../CommsPanel/CommsPanel'
import s from './BoardSection.module.css'

export interface BoardSectionProps {
  scope: BoardScope
  mainFeature: string
  preset: Preset
  direction: Direction
  size?: number
  onClose: (scope: BoardScope) => void
}

const NAME: Record<BoardScope, (mainFeature: string) => string> = {
  feature: (f) => f,
  project: () => 'pathly-adapters',
  global: () => 'all projects · all features',
}

// Board-view default asymmetric widths: Feature 50 · Project 30 · Global 20.
const BOARD_WEIGHT: Record<BoardScope, number> = { feature: 50, project: 30, global: 20 }

const SCOPE_ICONS: Record<BoardScope, React.ReactNode> = {
  feature: <GitBranch size={15} />,
  project: <Folder size={15} />,
  global:  <Globe size={15} />,
}

function getSectionFlex(props: BoardSectionProps): number | string {
  if (props.size) return `0 0 ${props.size}px`
  if (props.preset === 'board' && props.direction === 'row') return `${BOARD_WEIGHT[props.scope]} 1 0`
  return '1 1 0'
}

// A full-area section hosting one CommsPanel at a board scope.
// flex is injected as --section-flex CSS var (the one allowed inline exception).
export function BoardSection(props: BoardSectionProps) {
  const { scope, mainFeature, onClose } = props
  const sc = SCOPES[scope]
  const flexValue = getSectionFlex(props)

  return (
    <div
      className={s.board}
      data-board={scope}
      style={{ '--section-flex': flexValue } as React.CSSProperties}
    >
      <div className={s.bsHead}>
        <span className={s.bsIcon}>{SCOPE_ICONS[scope]}</span>
        <span className={s.bsScope}>{sc.title}</span>
        <span className={s.bsSep}>—</span>
        <span className={s.bsName}>{NAME[scope](mainFeature)}</span>
        <div className={s.bsHeadActs}>
          <button type="button" className={s.bsIconbtn} title="Attach artifact (coming soon)">
            <Plus size={15} />
          </button>
          <button
            type="button"
            className={`${s.bsIconbtn} ${s.close}`}
            title="Hide section"
            onClick={() => onClose(scope)}
          >
            <X size={15} />
          </button>
        </div>
      </div>
      <CommsPanel scope={scope} mainFeature={mainFeature} />
    </div>
  )
}
