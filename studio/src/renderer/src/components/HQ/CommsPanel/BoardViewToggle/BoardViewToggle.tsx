import { MessageSquare, ListTree, FileText } from 'lucide-react'
import s from './BoardViewToggle.module.css'

export type BoardView = 'messages' | 'goals' | 'artifacts'

const VIEWS: Array<{ id: BoardView; label: string; icon: JSX.Element }> = [
  { id: 'messages', label: 'Messages', icon: <MessageSquare size={12} /> },
  { id: 'goals', label: 'Goals & Tasks', icon: <ListTree size={12} /> },
  { id: 'artifacts', label: 'Artifacts', icon: <FileText size={12} /> },
]

interface Props {
  view: BoardView
  onChange: (v: BoardView) => void
}

// Segmented control under the search bar that switches the board's content
// between the message thread, the goal/task DAG, and the artifact list.
export function BoardViewToggle({ view, onChange }: Props): JSX.Element {
  return (
    <div className={s.row}>
      <div className={s.seg} role="tablist" aria-label="Board view">
        {VIEWS.map((v) => (
          <button
            key={v.id}
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
        ))}
      </div>
      {/* Right action slot — per-view actions (e.g. "+ New goal") land here later. */}
      <div className={s.actions} />
    </div>
  )
}
