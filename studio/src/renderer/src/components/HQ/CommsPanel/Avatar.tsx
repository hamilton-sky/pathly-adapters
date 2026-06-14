import React from 'react'
import type { AgentId } from '../../CommandCenter/types'
import { AGENTS } from '../../CommandCenter/constants'
import {
  SquareTerminal, Search, GitBranch, CircleCheck, History, Circle,
} from 'lucide-react'
import s from './Avatar.module.css'

// Agent icon map — lucide icons keyed by icon name from constants.
const ICONS: Record<string, React.ReactNode> = {
  'square-terminal': <SquareTerminal size={13} />,
  'search':          <Search size={13} />,
  'git-branch':      <GitBranch size={13} />,
  'circle-check':    <CircleCheck size={13} />,
  'history':         <History size={13} />,
}

// Agent avatar — gradient "YOU" chip for the human, a stage-coloured lucide
// glyph for each agent role. Color comes from data-agent CSS selector; no inline style.
export function Avatar({ from }: { from: AgentId }) {
  if (from === 'you') {
    return <span className={`${s.avatar} ${s.you}`}>YOU</span>
  }
  const a = AGENTS[from]
  const icon = a.icon ? (ICONS[a.icon] ?? <Circle size={13} />) : <Circle size={13} />
  return (
    <span className={s.avatar} data-agent={from}>
      {icon}
    </span>
  )
}
