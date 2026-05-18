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
      justifyContent: 'flex-end',
      padding: '6px 12px',
      backgroundColor: t.bgMantle,
      borderBottom: `1px solid ${t.bgSurface0}`,
      flexShrink: 0
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
