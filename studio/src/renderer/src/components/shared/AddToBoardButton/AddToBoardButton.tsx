// Icon (or labelled) button that opens a small board-target menu and posts the artifact to
// the CHOSEN board. USER-triggered — the generating agent never posts. Targets are supplied by
// the caller (Suggested · derived, Global, Project, each feature) so this stays presentational.

import React, { useState } from 'react'
import { LayoutDashboard } from 'lucide-react'
import BoardTargetMenu from './BoardTargetMenu'
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
  /** Disable without the green "on board" treatment (e.g. while a post is in flight). */
  disabled?: boolean
}

const MENU_W = 240

export default function AddToBoardButton({ onBoard, targets, onPick, label, disabled }: Props): JSX.Element {
  const [menu, setMenu] = useState<{ x: number; y: number } | null>(null)

  function open(e: React.MouseEvent<HTMLButtonElement>): void {
    // Adding is a COPY — a diagram can live on several boards, so being on one board never
    // locks the button; only an in-flight post (`disabled`) blocks it.
    if (disabled) return
    const r = e.currentTarget.getBoundingClientRect()
    // Estimate the menu height (title + scopes + capped feature scroll) to decide flip + clamp.
    const featureCount = targets.filter((t) => t.target.board === 'feature').length
    const h = 86 + Math.min(featureCount * 32, 200)
    const x = Math.max(8, Math.min(r.left, window.innerWidth - MENU_W - 8))
    const fitsBelow = r.bottom + 4 + h <= window.innerHeight - 8
    const y = fitsBelow ? r.bottom + 4 : Math.max(8, r.top - 4 - h)
    setMenu({ x, y })
  }

  return (
    <>
      <button
        type="button"
        className={s.btn}
        data-on-board={onBoard ? 'true' : 'false'}
        {...(label ? { 'data-labeled': 'true' } : {})}
        onClick={open}
        disabled={disabled}
        aria-label={onBoard ? 'On a board — add to another board' : 'Add to board'}
        title={onBoard ? 'On a board — add to another board' : 'Add to board'}
        {...(menu ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
      >
        <LayoutDashboard size={12} />
        {label && <span>{label}</span>}
      </button>
      {menu && (
        <BoardTargetMenu
          targets={targets}
          position={menu}
          onPick={onPick}
          onClose={() => setMenu(null)}
        />
      )}
    </>
  )
}
