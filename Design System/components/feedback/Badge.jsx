import React from 'react'

/**
 * Pathly Badge — small monospace chip. Tinted from a single colour
 * (text = colour, bg = 18% colour, border = 44% colour).
 */
const PRESETS = {
  core: 'var(--green)',
  flow: 'var(--runtime)',
  integration: 'var(--yellow)',
  body: 'var(--blue)',
  neutral: 'var(--text-muted)',
}

export function Badge({ label, children, color, variant, style }) {
  const c = color || PRESETS[variant] || 'var(--text-muted)'
  const s = {
    display: 'inline-flex', alignItems: 'center',
    padding: '1px 6px', borderRadius: 'var(--radius-sm)',
    fontFamily: 'var(--font-family-mono)', fontSize: 'var(--font-size-sm)',
    lineHeight: 1.5, color: c,
    border: `1px solid color-mix(in srgb, ${c} 35%, transparent)`,
    background: `color-mix(in srgb, ${c} 14%, transparent)`,
    ...style,
  }
  return <span className="pathly-badge" style={s}>{label ?? children}</span>
}
