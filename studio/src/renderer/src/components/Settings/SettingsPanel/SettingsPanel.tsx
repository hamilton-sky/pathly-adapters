import { useState, type ComponentType } from 'react'
import { SettingsNav, type SettingsGroup } from '../SettingsNav/SettingsNav'
import { AppearanceSettings } from '../AppearanceSettings/AppearanceSettings'
import { RunsSettings } from '../RunsSettings/RunsSettings'
import { IntelligenceSettings } from '../IntelligenceSettings/IntelligenceSettings'
import { SystemSettings } from '../SystemSettings/SystemSettings'
import s from './SettingsPanel.module.css'

// Settings shell: a left nav rail + a content panel that swaps on the active group.
// Each group owns its own state/hooks; this component holds only the active-group selection.
const PANELS: Record<SettingsGroup, ComponentType> = {
  appearance: AppearanceSettings,
  runs: RunsSettings,
  intelligence: IntelligenceSettings,
  system: SystemSettings,
}

export function SettingsPanel(): JSX.Element {
  const [active, setActive] = useState<SettingsGroup>('appearance')
  const Panel = PANELS[active]

  return (
    <div data-testid="settings-container" className={s.container}>
      <div className={s.header}>Settings</div>
      <div className={s.split}>
        <SettingsNav active={active} onSelect={setActive} />
        <div
          id="settings-content-panel"
          role="tabpanel"
          aria-labelledby={`settings-tab-${active}`}
          className={s.content}
        >
          <Panel />
        </div>
      </div>
    </div>
  )
}
