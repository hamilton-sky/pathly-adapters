import { LayoutGrid, Rows3 } from 'lucide-react'
import { SegmentedControl } from '../../../ConfigurePhaseModal/components/SegmentedControl/SegmentedControl'
import s from './MonitorBoardHeader.module.css'

export type BoardMode = 'live' | 'runs'

interface Props {
  running: number
  queued: number
  mode: BoardMode
  onMode: (m: BoardMode) => void
  view: 'grid' | 'banner'
  onView: (v: 'grid' | 'banner') => void
}

const MODE_OPTIONS: { value: BoardMode; label: string }[] = [
  { value: 'live', label: 'Live' },
  { value: 'runs', label: 'Runs' },
]

// Monitor board header: title · live/queued summary · Live/Runs mode toggle · card layout toggle
// (grid/rows — applies to BOTH modes: Live engine cards + Runs run cards) · a status pill honest
// per mode — SSE for the live board, "polls · 8s" for the DB-on-mount Runs list (never SSE in P0).
export function MonitorBoardHeader({ running, queued, mode, onMode, view, onView }: Props): JSX.Element {
  return (
    <header className={s.head}>
      <span className={s.title}>Monitor</span>
      <span className={s.summary}>{running} live · {queued} queued</span>

      <div className={s.modeToggle}>
        <SegmentedControl options={MODE_OPTIONS} value={mode} onChange={onMode} size="sm" />
      </div>

      <div className={s.viewToggle} role="group" aria-label="Card layout">
        <button
          type="button"
          className={s.viewBtn}
          data-active={view === 'grid'}
          onClick={() => onView('grid')}
          title="Grid of cards"
          aria-label="Grid view"
          {...(view === 'grid' ? { 'aria-pressed': 'true' } : { 'aria-pressed': 'false' })}
        >
          <LayoutGrid size={14} />
        </button>
        <button
          type="button"
          className={s.viewBtn}
          data-active={view === 'banner'}
          onClick={() => onView('banner')}
          title="Banner rows"
          aria-label="Banner view"
          {...(view === 'banner' ? { 'aria-pressed': 'true' } : { 'aria-pressed': 'false' })}
        >
          <Rows3 size={14} />
        </button>
      </div>

      <span className={mode === 'runs' ? s.poll : s.live}>
        <span className={s.dot} />{mode === 'runs' ? 'polls · 8s' : 'SSE live'}
      </span>
    </header>
  )
}
