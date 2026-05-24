import type { Theme } from '../../theme'

export const COMPLETED_GREEN = '#16A34A'
export const ACTIVE_CYAN = '#06B6D4'

export const PULSE_BORDER_CSS = `
@keyframes pathly-pulse-border {
  0%, 100% { border-left-color: ${ACTIVE_CYAN}; }
  50%       { border-left-color: rgba(6,182,212,0.15); }
}
.pathly-pulse-border { animation: none; border-left-color: ${ACTIVE_CYAN}; }
@media (prefers-reduced-motion: no-preference) {
  .pathly-pulse-border { animation: pathly-pulse-border 1.5s ease-in-out infinite; }
}
`

export function fsmStateColor(state: string, t: Theme): string {
  if (state === 'DONE') return t.green
  if (state === 'BUILDING' || state === 'REVIEWING') return t.runtime
  if (state === 'BLOCKED') return t.red
  return t.textMuted
}

export function statusBorderColor(status: string, t: Theme): string {
  if (status === 'DONE') return COMPLETED_GREEN
  if (status === 'IN_PROGRESS' || status === 'REVIEWING' || status === 'BUILDING') return ACTIVE_CYAN
  if (status === 'BLOCKED') return t.red
  return t.textMuted
}

export function statusBgColor(status: string): string {
  if (status === 'DONE') return 'rgba(166,227,161,0.05)'
  if (status === 'IN_PROGRESS' || status === 'REVIEWING' || status === 'BUILDING')
    return 'rgba(34,211,238,0.05)'
  if (status === 'BLOCKED') return 'rgba(243,139,168,0.05)'
  return 'rgba(108,112,134,0.05)'
}

export function statusIcon(status: string, t: Theme): { icon: string; color: string } {
  if (status === 'DONE') return { icon: '✓', color: COMPLETED_GREEN }
  if (status === 'IN_PROGRESS' || status === 'REVIEWING' || status === 'BUILDING')
    return { icon: '●', color: ACTIVE_CYAN }
  if (status === 'BLOCKED') return { icon: '✗', color: t.red }
  return { icon: '○', color: t.textMuted }
}

export function isActiveStatus(status: string): boolean {
  return status === 'IN_PROGRESS' || status === 'REVIEWING' || status === 'BUILDING'
}

export function makeStyles(t: Theme) {
  return {
    container: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column' as const,
      backgroundColor: t.bgBase,
      overflowY: 'auto' as const,
      height: '100%',
    },
    placeholder: {
      flex: 1,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: t.textMuted,
      fontSize: '15px',
      marginTop: '80px',
    },
    header: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '16px 24px',
      borderBottom: `1px solid ${t.bgSurface0}`,
      flexShrink: 0,
    },
    planName: {
      fontSize: '16px',
      fontWeight: 600,
      color: t.textPrimary,
    },
    fsmBadge: (state: string) => ({
      fontSize: '12px',
      fontWeight: 700,
      color: t.bgBase,
      padding: '2px 10px',
      borderRadius: '12px',
      backgroundColor: fsmStateColor(state, t),
    }),
    cardList: {
      padding: '16px 24px',
      display: 'flex',
      flexDirection: 'column' as const,
      gap: '10px',
    },
    eventRow: {
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
      fontSize: '12px',
      fontFamily: 'monospace',
      color: t.textSecondary,
      padding: '2px 0',
    },
    eventType:   { color: t.blue,      fontWeight: 600, flexShrink: 0 },
    eventAgent:  { color: t.accent,    flexShrink: 0 },
    eventResult: { color: t.green,     flexShrink: 0 },
    eventCost:   { color: t.yellow,    flexShrink: 0 },
    eventTime:   { color: t.textMuted, fontSize: '11px', marginLeft: 'auto' },
    recentEventsSection: {
      padding: '0 24px 16px 24px',
      display: 'flex',
      flexDirection: 'column' as const,
      gap: '4px',
    },
    recentEventsHeader: {
      fontSize: '12px',
      fontWeight: 600,
      color: t.textMuted,
      textTransform: 'uppercase' as const,
      letterSpacing: '0.05em',
      marginBottom: '6px',
    },
  }
}

export function makeCardStyles(
  t: Theme,
  borderColor: string,
  bgColor: string,
  iconColor: string,
) {
  return {
    card: {
      borderRadius: '6px',
      overflow: 'hidden' as const,
      minHeight: '52px',
      borderLeft: `3px solid ${borderColor}`,
      backgroundColor: bgColor,
      cursor: 'pointer',
      outline: 'none',
    },
    inner: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '10px 14px',
      gap: '8px',
    },
    left: {
      display: 'flex',
      alignItems: 'flex-start',
      gap: '8px',
      flex: 1,
      overflow: 'hidden',
    },
    statusIcon: {
      color: iconColor,
      fontWeight: 700,
      flexShrink: 0,
      fontSize: '14px',
    },
    textBlock: { flex: 1, overflow: 'hidden' },
    title: {
      fontSize: '14px',
      color: t.textPrimary,
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap' as const,
    },
    meta: {
      fontSize: '12px',
      color: t.textMuted,
      fontFamily: t.fontFamilyMono,
      marginTop: '2px',
      display: 'flex',
      gap: '8px',
      flexWrap: 'wrap' as const,
    },
    cost: {
      fontSize: '12px',
      color: t.textMuted,
      fontFamily: t.fontFamilyMono,
      fontVariantNumeric: 'tabular-nums' as const,
      marginTop: '2px',
    },
    statusBadge: {
      fontSize: '11px',
      fontWeight: 600,
      textTransform: 'uppercase' as const,
      color: borderColor,
      flexShrink: 0,
    },
  }
}
