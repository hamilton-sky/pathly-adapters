// Icon (or labelled) button that opens a small board-target menu and posts the artifact to
// the CHOSEN board. USER-triggered — the generating agent never posts. Targets are supplied by
// the caller (Suggested · derived, Global, Project, each feature) so this stays presentational.

import React, { useState } from 'react'
import { LayoutDashboard, Check } from 'lucide-react'
import { ContextMenu } from '../../ui/ContextMenu/ContextMenu'
import s from './AddToBoardButton.module.css'

/** A concrete board destination — the (feature, board, scope) triple apiPostArtifact needs. */
export interface BoardTarget {
  feature: string
  board: string
  scope: string
}

/** One menu choice; `suggested` marks the path-derived default (hoisted + tagged). */
export interface BoardTargetOption {
  key: string
  label: string
  target: BoardTarget
  suggested?: boolean
}

interface Props {
  onBoard: boolean
  targets: BoardTargetOption[]
  onPick: (target: BoardTarget) => void
  /** Optional text label (report style). Icon-only when omitted (card style). */
  label?: string
}

const MENU_W = 220

export default function AddToBoardButton({ onBoard, targets, onPick, label }: Props): JSX.Element {
  const [menu, setMenu] = useState<{ x: number; y: number } | null>(null)

  function open(e: React.MouseEvent<HTMLButtonElement>): void {
    if (onBoard) return
    const r = e.currentTarget.getBoundingClientRect()
    // Right-docked panel: clamp so a wide menu never spills off-screen.
    const x = Math.max(8, Math.min(r.left, window.innerWidth - MENU_W - 8))
    const h = Math.min(targets.length * 30 + 8, 260)
    const y = Math.min(r.bottom + 4, window.innerHeight - h - 8)
    setMenu({ x, y })
  }

  const items = targets.map((o) => ({
    label: o.suggested ? `${o.label} · suggested` : o.label,
    onClick: () => onPick(o.target),
  }))

  return (
    <>
      <button
        type="button"
        className={s.btn}
        data-on-board={onBoard ? 'true' : 'false'}
        {...(label ? { 'data-labeled': 'true' } : {})}
        onClick={open}
        disabled={onBoard}
        aria-label={onBoard ? 'On board' : 'Add to board'}
        title={onBoard ? 'On board' : 'Add to board'}
        {...(menu ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
      >
        {onBoard ? <Check size={12} /> : <LayoutDashboard size={12} />}
        {label && <span>{label}</span>}
      </button>
      {menu && <ContextMenu items={items} position={menu} onClose={() => setMenu(null)} />}
    </>
  )
}
