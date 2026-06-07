import React from 'react'

/**
 * Pathly IconButton — square icon-only control (topbar, toolbars, row actions).
 */
export function IconButton({
  children,
  title,
  variant = 'default',
  size = 'sm',
  active = false,
  disabled = false,
  onClick,
  style,
  ...rest
}) {
  const dim = size === 'md' ? '30px' : '26px'

  const color =
    variant === 'danger' ? 'var(--red)' :
    variant === 'muted' ? 'var(--text-muted)' :
    active ? 'var(--accent)' : 'var(--text-secondary)'

  const base = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: dim,
    height: dim,
    flexShrink: 0,
    borderRadius: 'var(--radius-md)',
    border: '1px solid transparent',
    background: active ? 'var(--accent-bg)' : 'transparent',
    color,
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.4 : 1,
    transition: 'background var(--transition-fast), color var(--transition-fast)',
    ...style,
  }

  const onEnter = (e) => { if (!disabled && !active) e.currentTarget.style.background = 'var(--bg-surface1)' }
  const onLeave = (e) => { if (!active) e.currentTarget.style.background = 'transparent' }

  return (
    <button
      type="button"
      className="pathly-icon-btn"
      title={title}
      aria-label={title}
      disabled={disabled}
      onClick={onClick}
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
      {...(active ? { 'data-active': 'true' } : {})}
      style={base}
      {...rest}
    >
      {children}
    </button>
  )
}
