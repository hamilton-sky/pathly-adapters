import { useState } from 'react'
import { useStore } from '../../store'
import { useRunnerStore } from '../../store/runnerStore'
import type { ThemeName } from '../../theme'
import { paletteLabels } from '../../theme'
import { PaletteSwatch } from './PaletteSwatch'
import { RadioCard } from './RadioCard'
import { NotificationSettings } from './NotificationSettings'
import { ExportSettings } from './ExportSettings'
import { CodeIntelligenceSettings } from './CodeIntelligenceSettings'
import { AiTargetSelector } from '../shared/AiTargetSelector/AiTargetSelector'
import { ProgressSelect } from '../shared/ProgressSelect/ProgressSelect'
import { useDefaultSummaryTarget } from './hooks/useDefaultSummaryTarget'
import { useDefaultProgress } from './hooks/useDefaultProgress'
import s from './Settings.module.css'

const DARK_PALETTES: ThemeName[] = ['dark', 'nord', 'mocha', 'solarized', 'dracula', 'rose-pine']
const LIGHT_PALETTES: ThemeName[] = ['light', 'solarized-light', 'latte', 'paper', 'rose-pine-dawn', 'mint']

export function Settings(): JSX.Element {
  const {
    preferredDark, preferredLight, setPreferredDark, setPreferredLight,
  } = useStore()

  const runnerMode = useRunnerStore((s) => s.runnerMode)
  const maxCostUsd = useRunnerStore((s) => s.maxCostUsd)
  const maxIterations = useRunnerStore((s) => s.maxIterations)
  const setRunnerMode = useRunnerStore((s) => s.setRunnerMode)
  const setRunConfig = useRunnerStore((s) => s.setRunConfig)

  const [costInput, setCostInput] = useState(String(maxCostUsd))
  const [iterInput, setIterInput] = useState(String(maxIterations))

  const { selection: summarySelection, setSelection: setSummarySelection } = useDefaultSummaryTarget()
  const { progress: defaultProgress, setProgress: setDefaultProgress } = useDefaultProgress()

  function saveRunConfig(): void {
    const cost = parseFloat(costInput)
    const iter = parseInt(iterInput, 10)
    if (!Number.isNaN(cost) && cost > 0) setRunConfig({ maxCostUsd: cost })
    if (!Number.isNaN(iter) && iter > 0) setRunConfig({ maxIterations: iter })
  }

  return (
    <div data-testid="settings-container" className={s.container}>
      <div className={s.header}>Settings</div>
      <div className={s.body}>

        <div className={s.section}>
          <div className={s.sectionTitle}>Color Palette</div>
          <div className={s.hint}>
            Select your preferred <strong>dark</strong> and <strong>light</strong> palette. The ☽/☀ toggle switches between them.
          </div>
          <div className={s.paletteGroupLabel}>
            Dark — <span className={s.accentText}>{paletteLabels[preferredDark]}</span>
          </div>
          <div data-testid="settings-palette-dark-swatches" className={s.swatchRowSpaced}>
            {DARK_PALETTES.map((name) => (
              <PaletteSwatch key={name} data-testid={`settings-palette-${name.replace(/\s+/g, '-').toLowerCase()}`} name={name} active={preferredDark === name} onClick={() => setPreferredDark(name)} />
            ))}
          </div>
          <div className={s.paletteGroupLabelBottom}>
            Light — <span className={s.accentText}>{paletteLabels[preferredLight]}</span>
          </div>
          <div data-testid="settings-palette-light-swatches" className={s.swatchRow}>
            {LIGHT_PALETTES.map((name) => (
              <PaletteSwatch key={name} data-testid={`settings-palette-${name.replace(/\s+/g, '-').toLowerCase()}`} name={name} active={preferredLight === name} onClick={() => setPreferredLight(name)} />
            ))}
          </div>
        </div>

        <div className={s.section}>
          <div className={s.sectionTitle}>Runner</div>
          <div className={s.hint}>
            Configure how pipeline stages are launched. Changes apply to the next run.
          </div>

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
          <div className={s.sectionTitle}>Summaries</div>
          <div className={s.hint}>
            Default model or CLI engine used to summarize .md artifacts added to boards.
          </div>
          <div className={s.summaryTarget}>
            <AiTargetSelector
              id="settings-summary-target"
              ariaLabel="Default summary AI target"
              value={summarySelection}
              onChange={setSummarySelection}
              allowOff
            />
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

        <CodeIntelligenceSettings />
        <ExportSettings />
        <NotificationSettings />

      </div>
    </div>
  )
}
