import { useState } from 'react'
import { useStore } from '../../store'
import type { ThemeName } from '../../theme'
import { paletteLabels } from '../../theme'
import { PaletteSwatch } from './PaletteSwatch'
import { RadioCard } from './RadioCard'
import s from './Settings.module.css'

const DARK_PALETTES: ThemeName[] = ['dark', 'nord', 'mocha', 'solarized', 'dracula', 'rose-pine']
const LIGHT_PALETTES: ThemeName[] = ['light', 'solarized-light', 'latte', 'paper', 'rose-pine-dawn', 'mint']

export function Settings(): JSX.Element {
  const {
    preferredDark, preferredLight, setPreferredDark, setPreferredLight,
    routingEngine, setRoutingEngine,
    mcpCommand, setMcpCommand,
  } = useStore()
  const [mcpInput, setMcpInput] = useState(mcpCommand)

  return (
    <div className={s.container}>
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
          <div className={s.swatchRowSpaced}>
            {DARK_PALETTES.map((name) => (
              <PaletteSwatch key={name} name={name} active={preferredDark === name} onClick={() => setPreferredDark(name)} />
            ))}
          </div>
          <div className={s.paletteGroupLabelBottom}>
            Light — <span className={s.accentText}>{paletteLabels[preferredLight]}</span>
          </div>
          <div className={s.swatchRow}>
            {LIGHT_PALETTES.map((name) => (
              <PaletteSwatch key={name} name={name} active={preferredLight === name} onClick={() => setPreferredLight(name)} />
            ))}
          </div>
        </div>

        <div className={s.section}>
          <div className={s.sectionTitle}>Routing Engine</div>
          <div className={s.radioGroup}>
            <RadioCard
              active={routingEngine === 'llm'}
              label="LLM driven"
              description="Orchestrator agent reads YAML and routes"
              onClick={() => setRoutingEngine('llm')}
            />
            <RadioCard
              active={routingEngine === 'python-mcp'}
              label="Python FSM"
              description="Deterministic MCP-driven FSM"
              onClick={() => setRoutingEngine('python-mcp')}
            />
          </div>
        </div>

        <div className={s.section}>
          <div className={s.sectionTitle}>MCP Server Command</div>
          <div className={s.inputRow}>
            <input
              aria-label="MCP server command"
              className={s.textInput}
              type="text"
              value={mcpInput}
              onChange={(e) => setMcpInput(e.target.value)}
            />
            <button type="button" className={s.saveBtn} onClick={() => setMcpCommand(mcpInput)}>
              Save
            </button>
          </div>
        </div>

      </div>
    </div>
  )
}
