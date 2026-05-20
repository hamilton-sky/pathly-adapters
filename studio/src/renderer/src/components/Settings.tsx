import { useState } from 'react'
import { useStore } from '../store'
import { useTheme } from '../useTheme'
import type { Theme, ThemeName } from '../theme'
import { themes, paletteLabels } from '../theme'

const DARK_PALETTES: ThemeName[] = ['dark', 'nord', 'mocha', 'solarized', 'dracula', 'rose-pine']
const LIGHT_PALETTES: ThemeName[] = ['light', 'solarized-light', 'latte', 'paper', 'rose-pine-dawn', 'mint']

function PaletteSwatch({ name, active, onClick }: { name: ThemeName; active: boolean; onClick: () => void }): JSX.Element {
  const p = themes[name]
  const label = paletteLabels[name]
  return (
    <div
      onClick={onClick}
      style={{
        cursor: 'pointer',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '6px',
        padding: '8px',
        borderRadius: '8px',
        border: active ? `2px solid ${p.accent}` : '2px solid transparent',
        backgroundColor: active ? `${p.accent}18` : 'transparent',
        transition: '150ms ease-out',
      }}
    >
      <div style={{
        width: '64px',
        height: '44px',
        borderRadius: '6px',
        overflow: 'hidden',
        border: `1px solid ${p.bgSurface0}`,
        display: 'flex',
        flexDirection: 'column',
      }}>
        <div style={{ flex: 1, backgroundColor: p.bgBase, display: 'flex', alignItems: 'center', padding: '4px 6px', gap: '4px' }}>
          <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: p.accent }} />
          <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: p.green }} />
          <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: p.red }} />
        </div>
        <div style={{ height: '16px', backgroundColor: p.bgTerminal }} />
      </div>
      <span style={{
        fontSize: '11px',
        fontWeight: active ? 600 : 400,
        color: active ? p.accent : p.textSecondary,
        whiteSpace: 'nowrap',
      }}>
        {label}
      </span>
    </div>
  )
}

function makeStyles(t: Theme): Record<string, React.CSSProperties> {
  return {
    container: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      backgroundColor: t.bgBase,
      color: t.textPrimary,
      overflowY: 'auto',
      height: '100%'
    },
    header: {
      padding: '20px 32px',
      borderBottom: `1px solid ${t.bgSurface0}`,
      fontSize: '18px',
      fontWeight: 600,
      color: t.textPrimary,
      flexShrink: 0
    },
    body: {
      padding: '24px 32px',
      display: 'flex',
      flexDirection: 'column',
      gap: '0'
    },
    section: {
      paddingBottom: '24px',
      marginBottom: '24px',
      borderBottom: `1px solid ${t.bgSurface0}`
    },
    sectionTitle: {
      fontSize: '13px',
      fontWeight: 600,
      color: t.textSecondary,
      textTransform: 'uppercase' as const,
      letterSpacing: '0.05em',
      marginBottom: '16px'
    },
    swatchRow: {
      display: 'flex',
      gap: '8px',
      flexWrap: 'wrap' as const,
    },
    radioGroup: {
      display: 'flex',
      gap: '12px'
    },
    radioCard: {
      display: 'flex',
      flexDirection: 'column' as const,
      gap: '4px',
      padding: '12px 16px',
      borderRadius: '6px',
      border: `1px solid ${t.bgSurface0}`,
      cursor: 'pointer',
      minWidth: '140px'
    },
    radioCardActive: {
      border: `1px solid ${t.accent}`,
      backgroundColor: `${t.accent}11`
    },
    radioLabel: {
      fontSize: '14px',
      fontWeight: 600,
      display: 'flex',
      alignItems: 'center',
      gap: '8px'
    },
    radioDesc: {
      fontSize: '12px',
      color: t.textMuted
    },
    inputRow: {
      display: 'flex',
      alignItems: 'center',
      gap: '10px'
    },
    textInput: {
      flex: 1,
      backgroundColor: t.bgMantle,
      border: `1px solid ${t.bgSurface0}`,
      borderRadius: '4px',
      color: t.textPrimary,
      fontSize: '13px',
      padding: '6px 10px',
      outline: 'none',
      fontFamily: 'monospace'
    },
    saveBtn: {
      background: t.accent,
      border: 'none',
      borderRadius: '4px',
      color: t.bgBase,
      cursor: 'pointer',
      padding: '6px 16px',
      fontSize: '13px',
      fontWeight: 600,
      flexShrink: 0
    }
  }
}

export function Settings(): JSX.Element {
  const { theme, preferredDark, preferredLight, setPreferredDark, setPreferredLight, routingEngine, setRoutingEngine, mcpCommand, setMcpCommand } = useStore()
  const t = useTheme()
  const styles = makeStyles(t)
  const [mcpInput, setMcpInput] = useState(mcpCommand)

  return (
    <div style={styles.container}>
      <div style={styles.header}>Settings</div>
      <div style={styles.body}>
        <div style={styles.section}>
          <div style={styles.sectionTitle}>Color Palette</div>
          <div style={{ fontSize: '11px', color: t.textMuted, marginBottom: '4px' }}>
            Select your preferred <strong>dark</strong> and <strong>light</strong> palette. The ☽/☀ toggle switches between them.
          </div>
          <div style={{ fontSize: '11px', color: t.textMuted, textTransform: 'uppercase' as const, letterSpacing: '0.06em', margin: '12px 0 6px' }}>
            Dark — <span style={{ color: t.accent }}>{paletteLabels[preferredDark]}</span>
          </div>
          <div style={{ ...styles.swatchRow, marginBottom: '12px' }}>
            {DARK_PALETTES.map((name) => (
              <PaletteSwatch key={name} name={name} active={preferredDark === name} onClick={() => setPreferredDark(name)} />
            ))}
          </div>
          <div style={{ fontSize: '11px', color: t.textMuted, textTransform: 'uppercase' as const, letterSpacing: '0.06em', marginBottom: '6px' }}>
            Light — <span style={{ color: t.accent }}>{paletteLabels[preferredLight]}</span>
          </div>
          <div style={styles.swatchRow}>
            {LIGHT_PALETTES.map((name) => (
              <PaletteSwatch key={name} name={name} active={preferredLight === name} onClick={() => setPreferredLight(name)} />
            ))}
          </div>
        </div>

        <div style={styles.section}>
          <div style={styles.sectionTitle}>Routing Engine</div>
          <div style={styles.radioGroup}>
            <div
              style={{ ...styles.radioCard, ...(routingEngine === 'llm' ? styles.radioCardActive : {}) }}
              onClick={() => setRoutingEngine('llm')}
            >
              <span style={{ ...styles.radioLabel, color: routingEngine === 'llm' ? t.accent : t.textPrimary }}>
                <span>{routingEngine === 'llm' ? '●' : '○'}</span> LLM driven
              </span>
              <span style={styles.radioDesc}>Orchestrator agent reads YAML and routes</span>
            </div>
            <div
              style={{ ...styles.radioCard, ...(routingEngine === 'python-mcp' ? styles.radioCardActive : {}) }}
              onClick={() => setRoutingEngine('python-mcp')}
            >
              <span style={{ ...styles.radioLabel, color: routingEngine === 'python-mcp' ? t.accent : t.textPrimary }}>
                <span>{routingEngine === 'python-mcp' ? '●' : '○'}</span> Python FSM
              </span>
              <span style={styles.radioDesc}>Deterministic MCP-driven FSM</span>
            </div>
          </div>
        </div>

        <div style={styles.section}>
          <div style={styles.sectionTitle}>MCP Server Command</div>
          <div style={styles.inputRow}>
            <input
              style={styles.textInput}
              type="text"
              value={mcpInput}
              onChange={(e) => setMcpInput(e.target.value)}
            />
            <button style={styles.saveBtn} onClick={() => setMcpCommand(mcpInput)}>
              Save
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
