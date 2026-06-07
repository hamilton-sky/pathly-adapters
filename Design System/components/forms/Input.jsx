import React from 'react'

/**
 * Pathly Input — single-line text field. Optional leading icon and label.
 */
export function Input({
  value,
  onChange,
  placeholder,
  label,
  icon = null,
  size = 'md',
  disabled = false,
  type = 'text',
  onKeyDown,
  style,
  ...rest
}) {
  const [focused, setFocused] = React.useState(false)
  const pad = size === 'sm' ? '5px 9px' : '7px 11px'
  const fontSize = size === 'sm' ? 'var(--font-size-sm)' : 'var(--font-size-base)'

  const wrap = {
    display: 'inline-flex', alignItems: 'center', gap: '7px',
    background: 'var(--bg-surface0)',
    border: focused ? '1px solid var(--accent)' : '1px solid var(--border-color)',
    borderRadius: 'var(--radius-md)',
    padding: pad,
    boxShadow: focused ? '0 0 0 2px var(--accent-bg)' : 'none',
    transition: 'border-color var(--transition-fast), box-shadow var(--transition-fast)',
    opacity: disabled ? 0.5 : 1,
    ...style,
  }
  const inputStyle = {
    flex: 1, minWidth: 0, border: 'none', outline: 'none', background: 'transparent',
    color: 'var(--text-primary)', fontFamily: 'var(--font-family-base)', fontSize,
  }

  const field = (
    <div className="pathly-input-wrap" style={wrap}>
      {icon ? <span style={{ display: 'inline-flex', color: 'var(--text-muted)', flexShrink: 0 }}>{icon}</span> : null}
      <input
        type={type} className="pathly-input" style={inputStyle}
        value={value} onChange={onChange} placeholder={placeholder}
        disabled={disabled} onKeyDown={onKeyDown}
        onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
        {...rest}
      />
    </div>
  )

  if (!label) return field
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
      <span style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', color: 'var(--text-muted)' }}>{label}</span>
      {field}
    </label>
  )
}
