import React from 'react'

/**
 * Pathly Card — the standard surface container. Optional header row with a
 * title and right-aligned actions. `interactive` adds a hover lift for
 * clickable cards (e.g. the DB Explorer feature grid).
 */
export function Card({
  title,
  actions,
  children,
  interactive = false,
  padding = '14px 16px',
  onClick,
  style,
}) {
  const [hover, setHover] = React.useState(false)
  const base = {
    background: 'var(--bg-surface0)',
    border: hover && interactive ? '1px solid var(--accent-border)' : 'var(--border)',
    borderRadius: 'var(--radius-lg)',
    cursor: interactive ? 'pointer' : 'default',
    transition: 'border-color var(--transition-fast), background var(--transition-fast)',
    overflow: 'hidden',
    ...style,
  }
  return (
    <div className="pathly-card" data-interactive={interactive ? 'true' : undefined}
      style={base} onClick={onClick}
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}>
      {(title || actions) && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          gap: '10px', padding: '11px 16px', borderBottom: 'var(--border-subtle)',
        }}>
          <span style={{ fontSize: 'var(--font-size-md)', fontWeight: 600, color: 'var(--text-primary)' }}>{title}</span>
          {actions && <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>{actions}</div>}
        </div>
      )}
      <div style={{ padding }}>{children}</div>
    </div>
  )
}
