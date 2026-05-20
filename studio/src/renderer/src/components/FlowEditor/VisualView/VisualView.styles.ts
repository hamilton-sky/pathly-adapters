import type { Theme } from '../../../theme'
import { Z } from '../zIndex'

export function makeVisualViewStyles(t: Theme): Record<string, React.CSSProperties> {
  const reducedMotion =
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches

  return {
    wrapper: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden'
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
    body: {
      flex: 1,
      display: 'flex',
      flexDirection: 'row',
      overflow: 'hidden'
    },
    canvas: {
      flex: 1,
      position: 'relative' as const,
      overflow: 'hidden'
    },
    inspectorPane: {
      width: '300px',
      flexShrink: 0,
      display: 'flex',
      flexDirection: 'column',
      zIndex: Z.inspector,
      backgroundColor: t.bgMantle,
      borderLeft: `1px solid ${t.bgSurface1}`,
      overflowY: 'auto' as const,
      transition: reducedMotion ? 'none' : 'width 200ms ease-out'
    }
  }
}
