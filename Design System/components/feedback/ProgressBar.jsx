import React from 'react'

/**
 * Pathly ProgressBar — thin rounded track with a coloured fill. Optional
 * fraction label (e.g. "3/3") shown to the right.
 */
export function ProgressBar({
  value = 0,
  max = 100,
  color = 'var(--accent)',
  height = 6,
  label,
  style,
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100))
  return (
    <div className="pathly-progress" style={{ display: 'flex', alignItems: 'center', gap: '8px', ...style }}>
      <div style={{ flex: 1, height: `${height}px`, background: 'var(--bg-surface1)', borderRadius: 'var(--radius-full)', overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 'var(--radius-full)', transition: 'width var(--transition-base)' }} />
      </div>
      {label != null && (
        <span style={{ fontFamily: 'var(--font-family-mono)', fontSize: 'var(--font-size-sm)', color: 'var(--text-muted)', flexShrink: 0 }}>{label}</span>
      )}
    </div>
  )
}
