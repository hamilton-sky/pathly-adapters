import React from 'react'
import { agentMeta } from '../../CommandCenter/constants'
import {
  SquareTerminal, Search, GitBranch, CircleCheck, History, Circle, User,
} from 'lucide-react'
import s from './Avatar.module.css'

// Agent icon map — lucide icons keyed by icon name from constants.
const ICONS: Record<string, React.ReactNode> = {
  'square-terminal': <SquareTerminal size={13} />,
  'search':          <Search size={13} />,
  'git-branch':      <GitBranch size={13} />,
  'circle-check':    <CircleCheck size={13} />,
  'history':         <History size={13} />,
  'user':            <User size={13} />,
}

// Agent avatar — a lucide glyph for every identity (the human gets a gradient
// "user" chip; each agent role a stage-coloured glyph). Color comes from the
// .you class or the data-agent CSS selector; no inline style.
export function Avatar({ from }: { from: string }) {
  const a = agentMeta(from)
  const icon = a.icon ? (ICONS[a.icon] ?? <Circle size={13} />) : <Circle size={13} />
  if (from === 'you') {
    return <span className={`${s.avatar} ${s.you}`}>{icon}</span>
  }
  return (
    <span className={s.avatar} data-agent={from}>
      {icon}
    </span>
  )
}
