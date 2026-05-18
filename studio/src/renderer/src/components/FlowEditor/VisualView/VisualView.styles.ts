import type { Theme } from '../../../theme'

export function makeVisualViewStyles(t: Theme): Record<string, React.CSSProperties> {
  return {
    wrapper: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden'
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
    canvas: {
      flex: 1,
      position: 'relative' as const,
      overflow: 'hidden'
    },
    detailPanel: {
      position: 'absolute' as const,
      top: 0,
      right: 0,
      bottom: 0,
      width: '220px',
      zIndex: 10,
      overflowY: 'auto' as const
    }
  }
}
