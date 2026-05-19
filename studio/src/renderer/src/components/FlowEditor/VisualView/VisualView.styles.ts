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
