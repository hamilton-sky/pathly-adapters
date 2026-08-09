import { Lock } from 'lucide-react'
import { ProgressSelect } from '../../shared/ProgressSelect/ProgressSelect'
import { useDefaultProgress } from '../hooks/useDefaultProgress'
import { useLoggingConfig } from './hooks/useLoggingConfig'
import s from './LoggingSettings.module.css'
import ss from '../Settings.module.css'

// Where agents narrate their work — the ONLY configurable logging sink. The cost/monitor spine
// (run history, cost tracking, gate liveness) is the control plane itself and is shown as a
// locked always-on row (SPEC §0 invariant). Verbosity shares board:default_progress with the
// Runs → Board updates control (single source of truth), so the two stay in sync.
export function LoggingSettings(): JSX.Element {
  const { boardEnabled, setBoardEnabled } = useLoggingConfig()
  const { progress, setProgress } = useDefaultProgress()

  return (
    <div className={ss.section}>
      <div className={ss.sectionTitle}>Logging</div>
      <div className={ss.hint}>
        Where agents narrate their work. Cost tracking and the run monitor are the control plane
        itself — always on, never a toggle.
      </div>

      <div className={s.row}>
        <button
          type="button"
          className={`${s.toggle} ${boardEnabled ? s.toggleOn : ''}`}
          onClick={() => setBoardEnabled(!boardEnabled)}
          aria-label={boardEnabled ? 'Disable board narration' : 'Enable board narration'}
          {...(boardEnabled ? { 'aria-pressed': 'true' } : { 'aria-pressed': 'false' })}
        />
        <div className={s.rowText}>
          <span className={s.rowLabel}>Board narration</span>
          <span className={s.rowDesc}>Agents post decisions, progress, and discoveries to the board.</span>
        </div>
      </div>

      <div className={s.verbosity}>
        <ProgressSelect
          id="logging-verbosity"
          label="Verbosity"
          value={progress}
          onChange={setProgress}
          disabled={!boardEnabled}
        />
      </div>

      <div className={s.row} data-locked="">
        <span className={s.lockBadge}>
          <Lock size={11} aria-hidden="true" /> Always on
        </span>
        <div className={s.rowText}>
          <span className={s.rowLabel}>Monitor + Cost</span>
          <span className={s.rowDesc}>
            Run history, cost tracking, and gate liveness — the control plane. Can’t be turned off.
          </span>
        </div>
      </div>
    </div>
  )
}
