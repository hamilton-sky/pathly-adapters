import type { ReactNode } from 'react'
import { Play, Square } from 'lucide-react'
import { Tooltip } from '../../ui'
import type { ActionProgress } from './progress'
import { fmtElapsed } from './progress'
import s from './RunPill.module.css'

export type PillState = 'idle' | 'running' | 'busy' | 'done' | 'error'

interface Props {
  /** Text shown when idle — "Run", "Evaluate", "AI Analyze", etc. */
  idleLabel: string
  state: PillState
  /** PTY-driven or tick-driven progress; provides elapsed clock + detail tooltip. */
  progress?: ActionProgress | null
  /** Optional leading icon (defaults to Play). */
  icon?: ReactNode
  onRun?: () => void
  /** When provided a Stop button appears to the right (not rendered at size="sm"). */
  onStop?: () => void
  disabled?: boolean
  /** sm = compact row (TaskCard), md = default (GoalRunButton). */
  size?: 'sm' | 'md'
}

export function RunPill({ idleLabel, state, progress, icon, onRun, onStop, disabled, size = 'md' }: Props): JSX.Element {
  const isRunning = state === 'running'
  const isActive = isRunning || state === 'busy'
  const iconSize = size === 'sm' ? 8 : 10

  // Label is fixed per state — timer is a separate fixed-width span (matches ActionPill)
  // so the button never reflows as digits tick 0:09 → 0:39 → 10:39.
  const label =
    state === 'idle'    ? idleLabel
    : state === 'running' ? `${idleLabel}…`
    : state === 'busy'    ? 'Busy'
    : state === 'done'    ? 'Done'
    :                       'Error'

  const timer = isRunning && progress != null ? fmtElapsed(progress.elapsedS) : null

  // Tooltip shows the latest PTY output line while running; otherwise the label.
  const tipLabel = isRunning && progress?.detail ? progress.detail : label

  const hasStop = !!onStop && size !== 'sm'

  return (
    <div className={s.pill} data-size={size !== 'md' ? size : undefined} {...(hasStop ? { 'data-has-stop': '' } : {})}>
      <Tooltip label={tipLabel} placement="top">
        <button
          type="button"
          className={s.run}
          data-state={state !== 'idle' ? state : undefined}
          disabled={disabled || isRunning || state === 'busy'}
          onClick={onRun}
          aria-label={timer ? `${label} ${timer}` : label}
        >
          {icon ?? <Play size={iconSize} />}
          <span className={s.label}>{label}</span>
          {timer && <span className={s.timer}>{timer}</span>}
        </button>
      </Tooltip>
      {onStop && size !== 'sm' && (
        <Tooltip label="Stop" placement="top">
          <button
            type="button"
            className={s.stop}
            disabled={!isActive}
            onClick={onStop}
            aria-label="Stop"
          >
            <Square size={8} />
          </button>
        </Tooltip>
      )}
    </div>
  )
}
