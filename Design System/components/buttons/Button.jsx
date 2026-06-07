import React from 'react'

/**
 * Pathly Button — the app-wide action button.
 *
 * Variants:
 *  - primary     accent-tinted fill (default interactive action)
 *  - cta         solid accent fill, dark text (high-emphasis, e.g. "Export Skill")
 *  - secondary   bordered, mantle bg, hover→accent (toolbar / FlowControlBar)
 *  - ghost       transparent, subtle border
 *  - destructive red-tinted
 */
export function Button({
  children,
  variant = 'primary',
  size = 'md',
  disabled = false,
  loading = false,
  icon = null,
  onClick,
  type = 'button',
  style,
  ...rest
}) {
  const pad = size === 'sm' ? '4px 10px' : '6px 14px'
  const fontSize = size === 'sm' ? 'var(--font-size-sm)' : 'var(--font-size-base)'

  const variants = {
    primary: {
      background: 'var(--accent-bg)',
      color: 'var(--accent)',
      border: '1px solid var(--accent-border)',
    },
    cta: {
      background: 'var(--accent)',
      color: 'var(--bg-mantle)',
      border: '1px solid transparent',
      fontWeight: 'var(--font-weight-semibold)',
    },
    secondary: {
      background: 'var(--bg-mantle)',
      color: 'var(--text-secondary)',
      border: '1px solid var(--border-color)',
    },
    ghost: {
      background: 'transparent',
      color: 'var(--text-secondary)',
      border: '1px solid var(--border-color)',
    },
    destructive: {
      background: 'var(--red-bg)',
      color: 'var(--red)',
      border: '1px solid var(--red-border)',
    },
  }

  const base = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '6px',
    padding: pad,
    borderRadius: 'var(--radius-md)',
    fontFamily: 'var(--font-family-base)',
    fontSize,
    fontWeight: 'var(--font-weight-medium)',
    lineHeight: 1,
    whiteSpace: 'nowrap',
    cursor: disabled || loading ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.5 : 1,
    transition: 'background var(--transition-base), color var(--transition-base), border-color var(--transition-base)',
    position: 'relative',
    ...variants[variant],
    ...style,
  }

  return (
    <button
      type={type}
      className={`pathly-btn pathly-btn--${variant}`}
      data-loading={loading ? 'true' : undefined}
      style={base}
      disabled={disabled || loading}
      onClick={onClick}
      {...rest}
    >
      {loading && (
        <span
          aria-hidden="true"
          style={{
            width: '12px', height: '12px', borderRadius: '50%',
            border: '2px solid transparent', borderTopColor: 'currentColor',
            animation: 'pathly-spin 0.7s linear infinite', marginRight: '-2px',
          }}
        />
      )}
      {icon && !loading ? <span style={{ display: 'inline-flex', flexShrink: 0 }}>{icon}</span> : null}
      {children}
      <style>{'@keyframes pathly-spin{to{transform:rotate(360deg)}}'}</style>
    </button>
  )
}
