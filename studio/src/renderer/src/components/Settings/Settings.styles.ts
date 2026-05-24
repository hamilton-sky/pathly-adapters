import type { Theme, ThemeName } from '../../theme'
import { themes } from '../../theme'

const DOT = { width: '8px', height: '8px', borderRadius: '50%' } as const

export function makeSwatchStyles(name: ThemeName, active: boolean) {
  const p = themes[name]
  return {
    wrapper: {
      cursor: 'pointer',
      display: 'flex',
      flexDirection: 'column' as const,
      alignItems: 'center',
      gap: '6px',
      padding: '8px',
      borderRadius: '8px',
      border: active ? `2px solid ${p.accent}` : '2px solid transparent',
      backgroundColor: active ? `${p.accent}18` : 'transparent',
      transition: '150ms ease-out',
    },
    preview: {
      width: '64px',
      height: '44px',
      borderRadius: '6px',
      overflow: 'hidden' as const,
      border: `1px solid ${p.bgSurface0}`,
      display: 'flex',
      flexDirection: 'column' as const,
    },
    topBar: {
      flex: 1,
      backgroundColor: p.bgBase,
      display: 'flex',
      alignItems: 'center',
      padding: '4px 6px',
      gap: '4px',
    },
    dotAccent: { ...DOT, backgroundColor: p.accent },
    dotGreen:  { ...DOT, backgroundColor: p.green },
    dotRed:    { ...DOT, backgroundColor: p.red },
    terminal: { height: '16px', backgroundColor: p.bgTerminal },
    label: {
      fontSize: '11px',
      fontWeight: active ? 600 : 400,
      color: active ? p.accent : p.textSecondary,
      whiteSpace: 'nowrap' as const,
    },
  }
}

export function makeStyles(t: Theme) {
  return {
    container: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column' as const,
      backgroundColor: t.bgBase,
      color: t.textPrimary,
      overflowY: 'auto' as const,
      height: '100%',
    },
    header: {
      padding: '20px 32px',
      borderBottom: `1px solid ${t.bgSurface0}`,
      fontSize: '18px',
      fontWeight: 600,
      color: t.textPrimary,
      flexShrink: 0,
    },
    body: {
      padding: '24px 32px',
      display: 'flex',
      flexDirection: 'column' as const,
      gap: '0',
    },
    section: {
      paddingBottom: '24px',
      marginBottom: '24px',
      borderBottom: `1px solid ${t.bgSurface0}`,
    },
    sectionTitle: {
      fontSize: '13px',
      fontWeight: 600,
      color: t.textSecondary,
      textTransform: 'uppercase' as const,
      letterSpacing: '0.05em',
      marginBottom: '16px',
    },
    hint: {
      fontSize: '11px',
      color: t.textMuted,
      marginBottom: '4px',
    },
    paletteGroupLabel: {
      fontSize: '11px',
      color: t.textMuted,
      textTransform: 'uppercase' as const,
      letterSpacing: '0.06em',
      margin: '12px 0 6px',
    },
    paletteGroupLabelBottom: {
      fontSize: '11px',
      color: t.textMuted,
      textTransform: 'uppercase' as const,
      letterSpacing: '0.06em',
      marginBottom: '6px',
    },
    swatchRow: {
      display: 'flex',
      gap: '8px',
      flexWrap: 'wrap' as const,
    },
    swatchRowSpaced: {
      display: 'flex',
      gap: '8px',
      flexWrap: 'wrap' as const,
      marginBottom: '12px',
    },
    radioGroup: {
      display: 'flex',
      gap: '12px',
    },
    radioCard: (active: boolean) => ({
      display: 'flex',
      flexDirection: 'column' as const,
      gap: '4px',
      padding: '12px 16px',
      borderRadius: '6px',
      border: active ? `1px solid ${t.accent}` : `1px solid ${t.bgSurface0}`,
      backgroundColor: active ? `${t.accent}11` : 'transparent',
      cursor: 'pointer',
      minWidth: '140px',
    }),
    radioLabel: (active: boolean) => ({
      fontSize: '14px',
      fontWeight: 600,
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      color: active ? t.accent : t.textPrimary,
    }),
    radioDesc: {
      fontSize: '12px',
      color: t.textMuted,
    },
    inputRow: {
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
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
      fontFamily: 'monospace',
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
      flexShrink: 0,
    },
    accentText: { color: t.accent },
  }
}
