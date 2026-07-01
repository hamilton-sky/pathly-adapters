import { useCodeContextSettings } from '../Settings/hooks/useCodeContextSettings'
import type { CodeContextReindex } from '../Settings/hooks/useCodeContextSettings'
import { useAutoCommitSetting } from '../HQ/FlowControlBar/hooks/useAutoCommitSetting'
import s from './CliMonitorBar.module.css'
import sc from './CodeIntelControl.module.css'

const REINDEX_OPTS: CodeContextReindex[] = ['off', 'stage', 'auto']

export function CodeIntelControl(): JSX.Element {
  const { backend, reindex, setBackend, setReindex } = useCodeContextSettings()
  const { enabled: autoCommit, toggle: toggleAutoCommit } = useAutoCommitSetting()

  return (
    <div className={sc.block}>
      <div className={s.sectionLabel}>CODE INTELLIGENCE</div>
      <div className={sc.row}>
        <span className={sc.fieldLabel}>Backend</span>
        <button
          type="button"
          role="switch"
          aria-checked={backend !== 'off' ? 'true' : 'false'}
          aria-label={backend !== 'off' ? 'Disable code intelligence backend' : 'Enable code intelligence backend'}
          className={`${sc.toggle} ${backend !== 'off' ? sc.toggleOn : ''}`}
          onClick={() => setBackend(backend !== 'off' ? 'off' : 'cli')}
        >
          <span className={sc.toggleThumb} />
        </button>
        <span className={sc.fieldLabel}>Re-index</span>
        <div className={sc.segmented}>
          {REINDEX_OPTS.map((opt) => (
            <button
              key={opt}
              type="button"
              aria-label={`Set re-index to ${opt}`}
              aria-pressed={reindex === opt ? 'true' : 'false'}
              className={`${sc.segBtn} ${reindex === opt ? sc.segBtnActive : ''}`}
              onClick={() => setReindex(opt)}
            >
              {opt}
            </button>
          ))}
        </div>
      </div>
      <div className={sc.row}>
        <span className={sc.fieldLabel}>Auto-commit</span>
        <button
          type="button"
          role="switch"
          aria-checked={autoCommit ? 'true' : 'false'}
          aria-label={autoCommit ? 'Disable auto-commit' : 'Enable auto-commit'}
          className={`${sc.toggle} ${autoCommit ? sc.toggleOn : ''}`}
          onClick={toggleAutoCommit}
          title="When on, the runner commits after the build stage. Off = changes stay in your working tree for review."
        >
          <span className={sc.toggleThumb} />
        </button>
      </div>
    </div>
  )
}
