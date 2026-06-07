import React from 'react'

/**
 * Pathly StatePill — the FSM stage pill (PLANNING · BUILDING · REVIEWING ·
 * TESTING · RETRO · DONE). A coloured dot + uppercase label, tinted to match.
 */
const STATE_COLORS = {
  PLANNING: 'var(--state-planning)',
  BUILDING: 'var(--state-building)',
  REVIEWING: 'var(--state-reviewing)',
  TESTING: 'var(--state-testing)',
  RETRO: 'var(--state-retro)',
  DONE: 'var(--state-done)',
  ERROR: 'var(--state-error)',
  IDLE: 'var(--text-muted)',
}

export function StatePill({ state = 'PLANNING', label, solid = false, style }) {
  const key = String(state).toUpperCase()
  const c = STATE_COLORS[key] || 'var(--text-muted)'
  const base = {
    display: 'inline-flex', alignItems: 'center', gap: '6px',
    padding: '3px 9px 3px 8px', borderRadius: 'var(--radius-full)',
    fontSize: 'var(--font-size-sm)', fontWeight: 600, letterSpacing: '0.04em',
    lineHeight: 1,
    color: solid ? 'var(--bg-mantle)' : c,
    background: solid ? c : `color-mix(in srgb, ${c} 13%, transparent)`,
    border: `1px solid color-mix(in srgb, ${c} ${solid ? 100 : 38}%, transparent)`,
    ...style,
  }
  return (
    <span className="pathly-state-pill" data-state={key} style={base}>
      <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: solid ? 'var(--bg-mantle)' : c, flexShrink: 0 }} />
      {label || key}
    </span>
  )
}
