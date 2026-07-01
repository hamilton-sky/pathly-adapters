import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { useCodeContextSettings } from '../Settings/hooks/useCodeContextSettings'
import type { CodeContextReindex } from '../Settings/hooks/useCodeContextSettings'
import { useAutoCommitSetting } from '../HQ/FlowControlBar/hooks/useAutoCommitSetting'
import sc from './CodeIntelControl.module.css'

const REINDEX_OPTS: CodeContextReindex[] = ['off', 'stage', 'auto']

export function CodeIntelControl(): JSX.Element {
  const { backend, reindex, setBackend, setReindex } = useCodeContextSettings()
  const { enabled: autoCommit, toggle: toggleAutoCommit } = useAutoCommitSetting()
  const [open, setOpen] = useState(false)
  const backendOn = backend !== 'off'

  return (
    <div className={sc.block}>
      {/* Collapsed by default — code intelligence is set-and-forget. */}
      <button
        type="button"
        className={sc.sectionToggle}
        onClick={() => setOpen((v) => !v)}
        {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
        aria-label="Toggle code intelligence settings"
      >
        {open ? <ChevronDown size={11} aria-hidden="true" /> : <ChevronRight size={11} aria-hidden="true" />}
        <span className={sc.toggleLabel}>CODE INTELLIGENCE</span>
        {!open && backendOn && <span className={sc.onDot} aria-hidden="true" />}
      </button>

      {open && (
        <>
          <div className={sc.rowPrimary}>
            <div className={sc.field}>
              <span className={sc.fieldLabel}>Backend</span>
              <button
                type="button"
                role="switch"
                aria-checked={backendOn ? 'true' : 'false'}
                aria-label={backendOn ? 'Disable code intelligence backend' : 'Enable code intelligence backend'}
                className={`${sc.toggle} ${backendOn ? sc.toggleOn : ''}`}
                onClick={() => setBackend(backendOn ? 'off' : 'cli')}
              >
                <span className={sc.toggleThumb} />
              </button>
            </div>
            <div className={sc.field}>
              <span className={sc.fieldLabel}>Auto-commit</span>
              <button
                type="button"
                role="switch"
                aria-checked={autoCommit ? 'true' : 'false'}
                aria-label={autoCommit ? 'Disable auto-commit' : 'Enable auto-commit'}
                className={`${sc.toggle} ${autoCommit ? sc.toggleOn : ''}`}
                onClick={toggleAutoCommit}
                title="When on, the runner commits after the build stage."
              >
                <span className={sc.toggleThumb} />
              </button>
            </div>
          </div>
          <div className={sc.rowSecondary}>
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
        </>
      )}
    </div>
  )
}
