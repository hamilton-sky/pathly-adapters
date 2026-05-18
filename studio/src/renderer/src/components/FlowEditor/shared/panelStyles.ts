import type { Theme } from '../../../theme'

export function makePanelStyles(t: Theme): Record<string, React.CSSProperties> {
  return {
    panel: {
      backgroundColor: t.bgMantle,
      borderLeft: t.borderSubtle,
      padding: '12px',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      gap: '8px'
    },
    header: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginBottom: '4px'
    },
    title: {
      fontWeight: 600,
      fontSize: 'var(--font-size-base)',
      color: t.accent
    },
    closeBtn: {
      background: 'none',
      border: 'none',
      color: t.textMuted,
      cursor: 'pointer',
      fontSize: 'var(--font-size-base)',
      padding: '0 4px'
    },
    label: {
      fontSize: '11px',
      color: t.textMuted,
      textTransform: 'uppercase' as const,
      letterSpacing: '0.5px'
    },
    input: {
      backgroundColor: t.bgSurface0,
      border: t.border,
      borderRadius: '4px',
      color: t.textPrimary,
      fontSize: 'var(--font-size-sm)',
      padding: '4px 6px',
      outline: 'none'
    },
    ruleRow: {
      display: 'flex',
      alignItems: 'center',
      gap: '4px',
      fontSize: 'var(--font-size-sm)'
    },
    actionRow: {
      display: 'flex',
      flexDirection: 'column' as const,
      gap: '2px',
      fontSize: 'var(--font-size-sm)'
    },
    ruleArtifact: {
      color: t.green,
      fontSize: '11px',
      wordBreak: 'break-all' as const
    },
    ruleArrow: {
      color: t.textMuted
    },
    ruleTarget: {
      color: t.blue,
      fontSize: '11px'
    },
    addBtn: {
      background: 'none',
      border: `1px dashed ${t.bgSurface1}`, /* divider, not border token */
      borderRadius: '4px',
      color: t.blue,
      cursor: 'pointer',
      fontSize: 'var(--font-size-sm)',
      padding: '4px 8px',
      marginTop: '4px'
    }
  }
}
