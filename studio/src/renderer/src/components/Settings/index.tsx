import { useState } from 'react'
import { useStore } from '../../store'
import { useTheme } from '../../useTheme'
import type { ThemeName } from '../../theme'
import { paletteLabels } from '../../theme'
import { makeStyles } from './Settings.styles'
import { PaletteSwatch } from './PaletteSwatch'
import { RadioCard } from './RadioCard'

const DARK_PALETTES: ThemeName[] = ['dark', 'nord', 'mocha', 'solarized', 'dracula', 'rose-pine']
const LIGHT_PALETTES: ThemeName[] = ['light', 'solarized-light', 'latte', 'paper', 'rose-pine-dawn', 'mint']

export function Settings(): JSX.Element {
  const {
    preferredDark, preferredLight, setPreferredDark, setPreferredLight,
    routingEngine, setRoutingEngine,
    mcpCommand, setMcpCommand,
  } = useStore()
  const s = makeStyles(useTheme())
  const [mcpInput, setMcpInput] = useState(mcpCommand)

  return (
    <div style={s.container}>
      <div style={s.header}>Settings</div>
      <div style={s.body}>

        <div style={s.section}>
          <div style={s.sectionTitle}>Color Palette</div>
          <div style={s.hint}>
            Select your preferred <strong>dark</strong> and <strong>light</strong> palette. The ☽/☀ toggle switches between them.
          </div>
          <div style={s.paletteGroupLabel}>
            Dark — <span style={s.accentText}>{paletteLabels[preferredDark]}</span>
          </div>
          <div style={s.swatchRowSpaced}>
            {DARK_PALETTES.map((name) => (
              <PaletteSwatch key={name} name={name} active={preferredDark === name} onClick={() => setPreferredDark(name)} />
            ))}
          </div>
          <div style={s.paletteGroupLabelBottom}>
            Light — <span style={s.accentText}>{paletteLabels[preferredLight]}</span>
          </div>
          <div style={s.swatchRow}>
            {LIGHT_PALETTES.map((name) => (
              <PaletteSwatch key={name} name={name} active={preferredLight === name} onClick={() => setPreferredLight(name)} />
            ))}
          </div>
        </div>

        <div style={s.section}>
          <div style={s.sectionTitle}>Routing Engine</div>
          <div style={s.radioGroup}>
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

        <div style={s.section}>
          <div style={s.sectionTitle}>MCP Server Command</div>
          <div style={s.inputRow}>
            <input
              aria-label="MCP server command"
              style={s.textInput}
              type="text"
              value={mcpInput}
              onChange={(e) => setMcpInput(e.target.value)}
            />
            <button type="button" style={s.saveBtn} onClick={() => setMcpCommand(mcpInput)}>
              Save
            </button>
          </div>
        </div>

      </div>
    </div>
  )
}
