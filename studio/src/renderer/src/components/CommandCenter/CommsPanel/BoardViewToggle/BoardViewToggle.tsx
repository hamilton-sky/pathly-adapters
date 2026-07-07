import type { ReactNode } from 'react'
import { MessageSquare, ListTree, FileText, LayoutGrid } from 'lucide-react'
import { Tooltip } from '../../../ui'
import s from './BoardViewToggle.module.css'

// Added 'grid' (the "All" overview). Because CommsPanel's boardView state is typed
// BoardView, widening it here widens it everywhere.
export type BoardView = 'messages' | 'goals' | 'artifacts' | 'grid'

const VIEWS: Array<{ id: BoardView; label: string; icon: JSX.Element }> = [
  { id: 'messages', label: 'Messages', icon: <MessageSquare size={12} /> },
  { id: 'goals', label: 'Goals & Tasks', icon: <ListTree size={12} /> },
  { id: 'artifacts', label: 'Artifacts', icon: <FileText size={12} /> },
  { id: 'grid', label: 'All', icon: <LayoutGrid size={12} /> },
]

interface Props {
  view: BoardView
  onChange: (v: BoardView) => void
  /** Per-view action rendered right-aligned in the toggle row (e.g. "+ New goal"). */
  rightAction?: ReactNode
}

// Segmented control under the search bar that switches the board's content between
// the message thread, the goal/task DAG, the artifact list, and the All grid.
export function BoardViewToggle({ view, onChange, rightAction }: Props): JSX.Element {
  return (
    <div className={s.row}>
      <div className={s.seg} role="tablist" aria-label="Board view">
        {VIEWS.map((v) => (
          <Tooltip key={v.id} label={v.label} placement="bottom">
            <button
              type="button"
              role="tab"
              className={s.segBtn}
              {...(view === v.id ? { 'data-on': '' } : {})}
              {...(view === v.id ? { 'aria-selected': 'true' } : { 'aria-selected': 'false' })}
              onClick={() => onChange(v.id)}
            >
              {v.icon}
              <span className={s.segLabel}>{v.label}</span>
            </button>
          </Tooltip>
        ))}
      </div>
      {/* Right action slot — per-view actions (e.g. "+ New goal"). Empty for 'grid'. */}
      <div className={s.actions}>{rightAction}</div>
    </div>
  )
}
