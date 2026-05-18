import type { Theme } from '../../theme'

export function makeFlowEditorStyles(t: Theme): Record<string, React.CSSProperties> {
  return {
    panel: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      backgroundColor: t.bgBase,
      overflow: 'hidden'
    },
    toolbar: {
      display: 'flex',
      alignItems: 'center',
      gap: '12px',
      padding: '6px 12px',
      backgroundColor: t.bgMantle,
      borderBottom: `1px solid ${t.bgSurface0}`,
      flexShrink: 0
    },
    tabs: {
      display: 'flex',
      gap: '4px'
    },
    tab: {
      background: 'none',
      border: `1px solid ${t.bgSurface1}`,
      borderRadius: '4px',
      color: t.textSecondary,
      cursor: 'pointer',
      padding: '3px 10px',
      fontSize: '12px'
    },
    tabActive: {
      background: t.bgSurface0,
      border: `1px solid ${t.accent}`,
      borderRadius: '4px',
      color: t.accent,
      cursor: 'pointer',
      padding: '3px 10px',
      fontSize: '12px'
    },
    error: {
      color: t.red,
      fontSize: '12px'
    },
    content: {
      flex: 1,
      display: 'flex',
      overflow: 'hidden'
    },
    message: {
      color: t.textMuted,
      fontSize: '15px',
      margin: 'auto'
    }
  }
}
