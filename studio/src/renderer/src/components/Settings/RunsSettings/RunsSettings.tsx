import { useState } from 'react'
import { useRunnerStore } from '../../../store/runnerStore'
import { RadioCard } from '../RadioCard'
import { ProgressSelect } from '../../shared/ProgressSelect/ProgressSelect'
import { useDefaultProgress } from '../hooks/useDefaultProgress'
import s from '../Settings.module.css'

export function RunsSettings(): JSX.Element {
  const runnerMode = useRunnerStore((st) => st.runnerMode)
  const maxCostUsd = useRunnerStore((st) => st.maxCostUsd)
  const maxIterations = useRunnerStore((st) => st.maxIterations)
  const setRunnerMode = useRunnerStore((st) => st.setRunnerMode)
  const setRunConfig = useRunnerStore((st) => st.setRunConfig)

  const [costInput, setCostInput] = useState(String(maxCostUsd))
  const [iterInput, setIterInput] = useState(String(maxIterations))
  const { progress: defaultProgress, setProgress: setDefaultProgress } = useDefaultProgress()

  function saveRunConfig(): void {
    const cost = parseFloat(costInput)
    const iter = parseInt(iterInput, 10)
    if (!Number.isNaN(cost) && cost > 0) setRunConfig({ maxCostUsd: cost })
    if (!Number.isNaN(iter) && iter > 0) setRunConfig({ maxIterations: iter })
  }

  return (
    <>
      <div className={s.section}>
        <div className={s.sectionTitle}>Runner</div>
        <div className={s.hint}>Configure how pipeline stages are launched. Changes apply to the next run.</div>

        <div className={s.runnerModeLabel}>Terminal mode</div>
        <div className={s.radioGroup}>
          <RadioCard
            data-testid="settings-runner-interactive"
            active={runnerMode === 'interactive'}
            label="Interactive"
            description="Visible PTY — PTY is killed when AGENT_DONE fires"
            onClick={() => setRunnerMode('interactive')}
          />
          <RadioCard
            data-testid="settings-runner-headless"
            active={runnerMode === 'headless'}
            label="Headless"
            description="Background run — waits for natural PTY exit"
            onClick={() => setRunnerMode('headless')}
          />
        </div>

        <div className={s.runnerFields}>
          <div className={s.runnerField}>
            <label className={s.runnerFieldLabel} htmlFor="settings-max-cost">Max cost (USD)</label>
            <input
              id="settings-max-cost"
              data-testid="settings-max-cost-input"
              aria-label="Max cost in USD"
              className={s.runnerInput}
              type="number"
              min="0.1"
              step="0.5"
              value={costInput}
              onChange={(e) => setCostInput(e.target.value)}
            />
          </div>
          <div className={s.runnerField}>
            <label className={s.runnerFieldLabel} htmlFor="settings-max-iter">Max iterations</label>
            <input
              id="settings-max-iter"
              data-testid="settings-max-iterations-input"
              aria-label="Max iterations"
              className={s.runnerInput}
              type="number"
              min="1"
              step="1"
              value={iterInput}
              onChange={(e) => setIterInput(e.target.value)}
            />
          </div>
          <button data-testid="settings-runner-save-btn" type="button" className={s.saveBtn} onClick={saveRunConfig}>
            Save
          </button>
        </div>
      </div>

      <div className={s.section}>
        <div className={s.sectionTitle}>Board updates</div>
        <div className={s.hint}>
          How chatty a headless agent is on the board — the default for every board run
          (single agent, Evaluate, decompose). Each run can still override it.
        </div>
        <div className={s.summaryTarget}>
          <ProgressSelect value={defaultProgress} onChange={setDefaultProgress} />
        </div>
      </div>
    </>
  )
}
