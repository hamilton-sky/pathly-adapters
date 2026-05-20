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
    },

    // NodePanel styles
    dangerBtn: {
      width: '100%',
      padding: '5px 0',
      background: 'none',
      border: `1px solid ${t.red}`,
      borderRadius: 4,
      color: t.red,
      fontSize: 12,
      cursor: 'pointer',
      flexShrink: 0,
    },
    renameRow: {
      display: 'flex',
      gap: 4,
      alignItems: 'center',
      marginTop: 4,
    },
    renameConfirmBtn: {
      background: 'none',
      border: `1px dashed ${t.accent}`,
      borderRadius: '4px',
      color: t.accent,
      cursor: 'pointer',
      fontSize: 'var(--font-size-sm)',
      padding: '3px 8px',
      marginTop: 0,
    },
    stateIdDisplay: {
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      marginTop: 4,
    },
    stateIdText: {
      fontSize: '12px',
      color: t.textSecondary,
      fontFamily: 'monospace',
    },
    editHint: {
      fontSize: '10px',
      color: t.textMuted,
    },
    agentChip: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 5,
      backgroundColor: t.bgSurface0,
      border: `1px solid ${t.bgSurface1}`,
      borderRadius: 12,
      fontSize: 12,
      padding: '3px 10px',
      color: t.textPrimary,
    },
    agentChipWarn: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 5,
      backgroundColor: t.bgSurface0,
      border: `1px solid ${t.yellow}`,
      borderRadius: 12,
      fontSize: 12,
      padding: '3px 10px',
      color: t.textPrimary,
    },
    agentWarnIcon: {
      color: t.yellow,
      fontSize: 10,
    },
    agentClearBtn: {
      background: 'none',
      border: 'none',
      color: t.textMuted,
      cursor: 'pointer',
      fontSize: 14,
      lineHeight: 1,
      padding: '0 2px',
    },
    behaviorList: {
      listStyle: 'none',
      margin: 0,
      padding: '2px 0',
      maxHeight: 180,
      overflowY: 'auto',
      border: `1px solid ${t.bgSurface1}`,
      borderRadius: 4,
      backgroundColor: t.bgSurface0,
    },
    behaviorItemDefault: {
      padding: '5px 10px',
      fontSize: 12,
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      backgroundColor: 'transparent',
      color: t.textPrimary,
      borderLeft: '2px solid transparent',
    },
    behaviorItemHighlighted: {
      padding: '5px 10px',
      fontSize: 12,
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      backgroundColor: t.bgSurface1,
      color: t.textPrimary,
      borderLeft: '2px solid transparent',
    },
    behaviorKindBadgeSkill: {
      fontSize: 9,
      fontWeight: 700,
      color: t.green,
      minWidth: 34,
      letterSpacing: '0.04em',
    },
    behaviorKindBadgeAgent: {
      fontSize: 9,
      fontWeight: 700,
      color: t.blue,
      minWidth: 34,
      letterSpacing: '0.04em',
    },
    behaviorCheckmark: {
      color: t.accent,
      fontSize: 11,
    },
    noAssigned: {
      fontSize: 12,
      color: t.textMuted,
      fontStyle: 'italic',
    },
    validationError: {
      fontSize: 11,
      color: t.red,
      padding: '3px 0',
    },
    validationWarning: {
      fontSize: 11,
      color: t.yellow,
      padding: '3px 0',
    },

    // EdgePanel styles
    section: {
      display: 'flex',
      flexDirection: 'column',
      gap: '6px',
    },
    condRow: {
      display: 'flex',
      alignItems: 'flex-start',
      justifyContent: 'space-between',
      gap: '4px',
      fontSize: '12px',
      backgroundColor: t.bgSurface0,
      borderRadius: '4px',
      padding: '6px 8px',
    },
    removeBtn: {
      background: 'none',
      border: 'none',
      color: t.textMuted,
      cursor: 'pointer',
      fontSize: '12px',
      padding: '0 2px',
      flexShrink: 0,
    },
    conditionBox: {
      backgroundColor: t.bgSurface0,
      borderRadius: '6px',
      padding: '8px',
    },
    condFormRow: {
      display: 'flex',
      gap: '6px',
      marginBottom: '6px',
    },
    condFormActions: {
      display: 'flex',
      gap: '6px',
      justifyContent: 'flex-end',
    },
    condTarget: {
      color: t.blue,
    },
    condArtifact: {
      color: t.green,
    },
    condText: {
      color: t.textSecondary,
      fontSize: '11px',
    },
    actionEditRow: {
      display: 'flex',
      alignItems: 'flex-start',
      justifyContent: 'space-between',
      gap: '4px',
      fontSize: '12px',
      backgroundColor: t.bgSurface0,
      borderRadius: '4px',
      padding: '6px 8px',
      flexDirection: 'column' as const,
    },
    actionDisplayRow: {
      display: 'flex',
      alignItems: 'flex-start',
      justifyContent: 'space-between',
      gap: '4px',
      fontSize: '12px',
      backgroundColor: t.bgSurface0,
      borderRadius: '4px',
      padding: '6px 8px',
      cursor: 'pointer',
    },
    actionDisplayRowReadOnly: {
      display: 'flex',
      alignItems: 'flex-start',
      justifyContent: 'space-between',
      gap: '4px',
      fontSize: '12px',
      backgroundColor: t.bgSurface0,
      borderRadius: '4px',
      padding: '6px 8px',
      cursor: 'default',
    },
    actionSkillActive: {
      color: t.green,
      fontSize: '11px',
    },
    actionSkillEmpty: {
      color: t.textMuted,
      fontSize: '11px',
    },
    actionMsg: {
      color: t.textSecondary,
      fontSize: '11px',
    },
    actionEditActions: {
      display: 'flex',
      gap: 4,
      justifyContent: 'flex-end',
    },
    cancelEditBtn: {
      background: 'none',
      border: 'none',
      color: t.textMuted,
      cursor: 'pointer',
      fontSize: '12px',
      padding: '0 2px',
      flexShrink: 0,
    },
    saveEditBtn: {
      background: 'none',
      border: 'none',
      color: t.accent,
      cursor: 'pointer',
      fontSize: '12px',
      padding: '0 2px',
      flexShrink: 0,
    },
    condSelectStyle: {
      flex: 1,
      backgroundColor: t.bgSurface1,
      border: t.border,
      borderRadius: '4px',
      color: t.textPrimary,
      fontSize: '12px',
      padding: '4px',
    },
  }
}
