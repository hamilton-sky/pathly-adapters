import type { CSSProperties } from 'react'
import type { Theme } from '../../theme'

export function makeStyles(t: Theme): Record<string, CSSProperties> {
  return {
    overlay: {
      position: 'fixed',
      inset: 0,
      backgroundColor: 'rgba(0,0,0,0.7)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000
    },
    card: {
      width: '600px',
      maxHeight: '80vh',
      backgroundColor: t.bgMantle,
      border: `1px solid ${t.bgSurface0}`,
      borderRadius: '8px',
      display: 'flex',
      flexDirection: 'column'
    },
    stepIndicator: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '8px',
      padding: '16px 24px',
      borderBottom: `1px solid ${t.bgSurface0}`,
      flexShrink: 0
    },
    stepConnector: {
      flex: 1,
      height: '1px',
      backgroundColor: t.bgSurface0,
      maxWidth: '40px'
    },
    content: {
      flex: 1,
      overflowY: 'auto',
      padding: '24px'
    },
    stepHeader: {
      fontSize: '16px',
      fontWeight: 600,
      color: t.textPrimary,
      marginBottom: '4px'
    },
    stepSub: {
      fontSize: '12px',
      color: t.textMuted,
      marginBottom: '20px'
    },
    label: {
      display: 'block',
      fontSize: '12px',
      color: t.textSecondary,
      marginBottom: '6px',
      fontWeight: 600
    },
    input: {
      width: '100%',
      boxSizing: 'border-box' as const,
      backgroundColor: t.bgBase,
      border: `1px solid ${t.bgSurface0}`,
      borderRadius: '4px',
      color: t.textPrimary,
      fontSize: '13px',
      padding: '8px 10px',
      outline: 'none',
      marginBottom: '16px',
      fontFamily: 'inherit'
    },
    textarea: {
      width: '100%',
      boxSizing: 'border-box' as const,
      backgroundColor: t.bgBase,
      border: `1px solid ${t.bgSurface0}`,
      borderRadius: '4px',
      color: t.textPrimary,
      fontSize: '13px',
      padding: '8px 10px',
      outline: 'none',
      marginBottom: '16px',
      resize: 'vertical' as const,
      minHeight: '80px',
      fontFamily: 'inherit'
    },
    stateRow: {
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      marginBottom: '8px'
    },
    stateInput: {
      flex: 1,
      backgroundColor: t.bgBase,
      border: `1px solid ${t.bgSurface0}`,
      borderRadius: '4px',
      color: t.textPrimary,
      fontSize: '13px',
      padding: '6px 10px',
      outline: 'none',
      fontFamily: 'monospace'
    },
    removeBtn: {
      background: 'none',
      border: 'none',
      color: t.textMuted,
      cursor: 'pointer',
      fontSize: '16px',
      padding: '0 4px',
      lineHeight: 1,
      flexShrink: 0
    },
    addBtn: {
      background: 'none',
      border: `1px dashed ${t.bgSurface1}`,
      borderRadius: '4px',
      color: t.blue,
      cursor: 'pointer',
      fontSize: '12px',
      padding: '6px 12px',
      marginTop: '4px'
    },
    stateTag: {
      fontSize: '11px',
      color: t.textMuted,
      flexShrink: 0
    },
    transitionRow: {
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      marginBottom: '8px'
    },
    select: {
      backgroundColor: t.bgBase,
      border: `1px solid ${t.bgSurface0}`,
      borderRadius: '4px',
      color: t.textPrimary,
      fontSize: '12px',
      padding: '5px 8px',
      outline: 'none',
      cursor: 'pointer'
    },
    transitionArrow: {
      color: t.textMuted,
      flexShrink: 0
    },
    transitionLabelInput: {
      width: '100px',
      backgroundColor: t.bgBase,
      border: `1px solid ${t.bgSurface0}`,
      borderRadius: '4px',
      color: t.textPrimary,
      fontSize: '12px',
      padding: '5px 8px',
      outline: 'none'
    },
    agentRow: {
      display: 'flex',
      alignItems: 'center',
      gap: '12px',
      marginBottom: '10px'
    },
    agentStateName: {
      width: '120px',
      fontSize: '12px',
      color: t.textSecondary,
      fontFamily: 'monospace',
      flexShrink: 0
    },
    agentInput: {
      flex: 1,
      backgroundColor: t.bgBase,
      border: `1px solid ${t.bgSurface0}`,
      borderRadius: '4px',
      color: t.textPrimary,
      fontSize: '12px',
      padding: '5px 8px',
      outline: 'none',
      fontFamily: 'monospace'
    },
    terminalNote: {
      fontSize: '12px',
      color: t.textMuted,
      fontStyle: 'italic'
    },
    preBlock: {
      backgroundColor: t.bgBase,
      border: `1px solid ${t.bgSurface0}`,
      borderRadius: '4px',
      padding: '12px',
      fontSize: '12px',
      fontFamily: 'monospace',
      color: t.textPrimary,
      overflowX: 'auto',
      whiteSpace: 'pre' as const,
      maxHeight: '240px',
      overflowY: 'auto'
    },
    storageRow: {
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      marginTop: '16px'
    },
    storageLabel: {
      fontSize: '12px',
      color: t.textSecondary,
      flexShrink: 0
    },
    storageInput: {
      flex: 1,
      backgroundColor: t.bgBase,
      border: `1px solid ${t.bgSurface0}`,
      borderRadius: '4px',
      color: t.textPrimary,
      fontSize: '12px',
      padding: '5px 8px',
      outline: 'none',
      fontFamily: 'monospace'
    },
    btnRow: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '16px 24px',
      borderTop: `1px solid ${t.bgSurface0}`,
      flexShrink: 0
    },
    backBtn: {
      background: 'none',
      border: `1px solid ${t.bgSurface1}`,
      borderRadius: '4px',
      color: t.textSecondary,
      cursor: 'pointer',
      padding: '6px 16px',
      fontSize: '13px'
    },
    nextBtn: {
      background: t.accent,
      border: 'none',
      borderRadius: '4px',
      color: t.bgBase,
      cursor: 'pointer',
      padding: '6px 16px',
      fontSize: '13px',
      fontWeight: 600
    },
    cancelBtn: {
      background: 'none',
      border: 'none',
      color: t.textMuted,
      cursor: 'pointer',
      padding: '6px 10px',
      fontSize: '13px'
    },
    error: {
      color: t.red,
      fontSize: '12px',
      marginTop: '4px'
    }
  }
}

export function stepDotStyle(t: Theme, active: boolean, done: boolean): CSSProperties {
  return {
    width: '28px',
    height: '28px',
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '13px',
    fontWeight: 600,
    backgroundColor: done ? t.green : active ? t.accent : t.bgSurface0,
    color: done || active ? t.bgBase : t.textMuted,
    flexShrink: 0
  }
}
