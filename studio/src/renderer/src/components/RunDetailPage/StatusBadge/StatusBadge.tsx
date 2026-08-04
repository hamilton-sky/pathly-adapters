import s from './StatusBadge.module.css'

interface Props {
  /** run_history lifecycle status (running | done | error | aborted | paused | queued | …). */
  status: string
}

// Tinted pill for a run's lifecycle status. LOCAL to the run page — Monitor's EngineStatus union is
// only running/queued/done/failed, whereas run_history also carries error/aborted/paused. Unknown
// values fall through to the neutral base style rather than throwing off an enum.
export function StatusBadge({ status }: Props): JSX.Element {
  const key = (status || '').toLowerCase()
  return (
    <span className={s.badge} data-status={key}>
      {key || 'unknown'}
    </span>
  )
}
