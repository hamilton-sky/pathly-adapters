import { useState } from 'react'
import { useStore } from '../store'
import { useTheme } from '../useTheme'
import type { Theme } from '../theme'

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
  const { theme, setTheme, routingEngine, setRoutingEngine, mcpCommand, setMcpCommand } = useStore()
  const t = useTheme()
  const styles = makeStyles(t)
  const [mcpInput, setMcpInput] = useState(mcpCommand)

  return (
    <div style={styles.container}>
      <div style={styles.header}>Settings</div>
      <div style={styles.body}>
        <div style={styles.section}>
          <div style={styles.sectionTitle}>Theme</div>
          <div style={styles.radioGroup}>
            <div
              style={{ ...styles.radioCard, ...(theme === 'dark' ? styles.radioCardActive : {}) }}
              onClick={() => setTheme('dark')}
            >
              <span style={{ ...styles.radioLabel, color: theme === 'dark' ? t.accent : t.textPrimary }}>
                <span>{theme === 'dark' ? '●' : '○'}</span> Dark
              </span>
            </div>
            <div
              style={{ ...styles.radioCard, ...(theme === 'light' ? styles.radioCardActive : {}) }}
              onClick={() => setTheme('light')}
            >
              <span style={{ ...styles.radioLabel, color: theme === 'light' ? t.accent : t.textPrimary }}>
                <span>{theme === 'light' ? '●' : '○'}</span> Light
              </span>
            </div>
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
