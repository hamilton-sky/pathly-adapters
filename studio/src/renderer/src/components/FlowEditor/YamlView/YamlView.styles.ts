import type { Theme } from '../../../theme'

export function makeYamlViewStyles(t: Theme): Record<string, React.CSSProperties> {
  return {
    wrapper: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden'
    },
    errorBanner: {
      backgroundColor: `${t.red}33`,
      borderBottom: `1px solid ${t.red}`,
      padding: '6px 12px',
      flexShrink: 0
    },
    errorText: {
      color: t.red,
      fontSize: '12px',
      fontFamily: 'monospace'
    },
    toolbar: {
      display: 'flex',
      alignItems: 'center',
      gap: '6px',
      padding: '6px 12px',
      backgroundColor: t.bgMantle,
      borderBottom: `1px solid ${t.bgSurface0}`,
      flexShrink: 0
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
    saveBtn: {
      background: t.accent,
      border: 'none',
      borderRadius: '4px',
      color: t.bgBase,
      cursor: 'pointer',
      padding: '4px 14px',
      fontSize: '13px',
      fontWeight: 600
    },
    saveBtnDisabled: {
      background: t.bgSurface1,
      border: 'none',
      borderRadius: '4px',
      color: t.textMuted,
      cursor: 'not-allowed',
      padding: '4px 14px',
      fontSize: '13px',
      fontWeight: 600
    },
    editor: {
      flex: 1,
      overflow: 'auto'
    }
  }
}
