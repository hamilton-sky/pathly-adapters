import type { Theme } from '../../../theme'
import { Z } from '../zIndex'

export function makeVisualViewStyles(t: Theme): Record<string, React.CSSProperties> {
  const reducedMotion =
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches

  const baseBtnRadius: React.CSSProperties = {
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    padding: '4px 14px',
    fontSize: '13px',
    fontWeight: 600,
  }

  return {
    // ── layout ──────────────────────────────────────────────────────────────
    wrapper: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    },
    body: {
      flex: 1,
      display: 'flex',
      flexDirection: 'row',
      overflow: 'hidden',
    },
    canvas: {
      flex: 1,
      position: 'relative' as const,
      overflow: 'hidden',
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
      transition: reducedMotion ? 'none' : 'width 200ms ease-out',
    },

    // ── toolbar ─────────────────────────────────────────────────────────────
    toolbar: {
      display: 'flex',
      alignItems: 'center',
      gap: '6px',
      padding: '6px 12px',
      backgroundColor: t.bgMantle,
      borderBottom: `1px solid ${t.bgSurface0}`,
      flexShrink: 0,
    },
    toolbarDivider: {
      width: 1,
      height: 20,
      background: t.bgSurface1,
      margin: '0 6px',
      alignSelf: 'center',
    },
    toolbarSpacer: {
      flex: 1,
    },
    tab: {
      background: 'none',
      border: `1px solid ${t.bgSurface1}`,
      borderRadius: '4px',
      color: t.textSecondary,
      cursor: 'pointer',
      padding: '3px 10px',
      fontSize: '12px',
    },
    tabActive: {
      background: t.bgSurface0,
      border: `1px solid ${t.accent}`,
      borderRadius: '4px',
      color: t.accent,
      cursor: 'pointer',
      padding: '3px 10px',
      fontSize: '12px',
    },
    saveBtn: {
      ...baseBtnRadius,
      background: t.accent,
      color: t.bgBase,
    },
    ghostBtn: {
      ...baseBtnRadius,
      background: 'transparent',
      color: t.textMuted,
      border: `1px solid ${t.bgSurface1}`,
    },

    // ── export controls ─────────────────────────────────────────────────────
    exportSelect: {
      background: t.bgSurface0,
      color: t.textPrimary,
      border: `1px solid ${t.bgSurface1}`,
      borderRadius: 4,
      padding: '3px 8px',
      fontSize: 13,
      cursor: 'pointer',
    },
    publishBtn: {
      ...baseBtnRadius,
      background: t.accent,
      color: t.bgBase,
      cursor: 'pointer',
    },
    publishBtnDisabled: {
      ...baseBtnRadius,
      background: t.bgSurface1,
      color: t.textMuted,
      cursor: 'not-allowed',
    },

    // ── export toast ─────────────────────────────────────────────────────────
    toast: {
      position: 'fixed',
      bottom: 24,
      right: 24,
      background: t.bgSurface1,
      color: t.textPrimary,
      border: `1px solid ${t.bgSurface0}`,
      borderRadius: 6,
      padding: '8px 16px',
      fontSize: 13,
      zIndex: 60,
      boxShadow: '0 2px 8px rgba(0,0,0,0.4)',
      display: 'flex',
      alignItems: 'center',
      gap: 12,
    },
    toastCopyBtn: {
      background: 'none',
      border: 'none',
      color: t.accent,
      cursor: 'pointer',
      fontSize: 12,
    },

    // ── last export hint ─────────────────────────────────────────────────────
    lastExportHint: {
      padding: '2px 12px',
      fontSize: 11,
      color: t.textMuted,
      backgroundColor: t.bgMantle,
      borderBottom: `1px solid ${t.bgSurface0}`,
      flexShrink: 0,
    },

    // ── export confirm modal ─────────────────────────────────────────────────
    confirmOverlay: {
      position: 'fixed',
      inset: 0,
      background: 'rgba(0,0,0,0.6)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 100,
    },
    confirmModal: {
      background: t.bgMantle,
      border: `1px solid ${t.bgSurface1}`,
      borderRadius: 8,
      padding: 24,
      maxWidth: 400,
      width: '100%',
    },
    confirmText: {
      color: t.textPrimary,
      marginBottom: 8,
      fontSize: 14,
    },
    confirmSubtext: {
      color: t.textMuted,
      marginBottom: 16,
      fontSize: 12,
    },
    confirmActions: {
      display: 'flex',
      gap: 8,
      justifyContent: 'flex-end',
    },
    cancelBtn: {
      ...baseBtnRadius,
      background: t.bgSurface0,
      color: t.textMuted,
    },
    confirmBtn: {
      ...baseBtnRadius,
      background: t.accent,
      color: '#fff',
    },

    // ── empty canvas hint ────────────────────────────────────────────────────
    emptyOverlay: {
      position: 'absolute',
      inset: 0,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 8,
      pointerEvents: 'none',
      zIndex: 1,
    },
    emptyBox: {
      border: `2px dashed ${t.bgSurface1}`,
      borderRadius: 12,
      padding: '24px 32px',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 8,
    },
    emptyText: {
      fontSize: 13,
      color: t.textMuted,
    },
    emptySubtext: {
      fontSize: 11,
      color: t.textMuted,
    },
    emptySubtextAccent: {
      color: t.textSecondary,
    },

    // ── context menus ────────────────────────────────────────────────────────
    contextBackdrop: {
      position: 'fixed',
      inset: 0,
      zIndex: 39,
    },
    contextMenu: {
      position: 'fixed',
      background: t.bgMantle,
      border: `1px solid ${t.bgSurface1}`,
      borderRadius: 6,
      boxShadow: '0 2px 8px rgba(0,0,0,0.4)',
      zIndex: 40,
      minWidth: 160,
      padding: '4px 0',
    },
    contextMenuBtn: {
      display: 'block',
      width: '100%',
      textAlign: 'left',
      padding: '6px 14px',
      background: 'none',
      border: 'none',
      color: t.red,
      fontSize: 13,
      cursor: 'pointer',
    },
  }
}
