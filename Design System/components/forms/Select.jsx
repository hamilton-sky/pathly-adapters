import React from 'react'

/**
 * Pathly Select — native dropdown styled to match Input. Pass an array of
 * { value, label } options (or plain strings).
 */
export function Select({
  value,
  onChange,
  options = [],
  size = 'md',
  disabled = false,
  style,
  ...rest
}) {
  const pad = size === 'sm' ? '5px 28px 5px 9px' : '7px 30px 7px 11px'
  const fontSize = size === 'sm' ? 'var(--font-size-sm)' : 'var(--font-size-base)'
  const opts = options.map((o) => (typeof o === 'string' ? { value: o, label: o } : o))

  const chevron =
    "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%238899B0' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='m6 9 6 6 6-6'/></svg>"

  const sel = {
    appearance: 'none', WebkitAppearance: 'none',
    background: `var(--bg-surface0) url("${chevron}") no-repeat right 9px center`,
    border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)',
    color: 'var(--text-primary)', fontFamily: 'var(--font-family-base)', fontSize,
    padding: pad, cursor: disabled ? 'not-allowed' : 'pointer', outline: 'none',
    opacity: disabled ? 0.5 : 1, ...style,
  }

  return (
    <select className="pathly-select" style={sel} value={value} onChange={onChange} disabled={disabled} {...rest}>
      {opts.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  )
}
