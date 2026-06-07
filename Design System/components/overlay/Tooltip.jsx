import React from 'react'

/**
 * Pathly Tooltip — hover label on a wrapped trigger. Optional description
 * and keyboard shortcut. Dark surface, appears after a short delay.
 */
export function Tooltip({ label, description, shortcut, placement = 'bottom', children, style }) {
  const [show, setShow] = React.useState(false)
  const timer = React.useRef(null)

  const enter = () => { timer.current = setTimeout(() => setShow(true), 350) }
  const leave = () => { clearTimeout(timer.current); setShow(false) }

  const pos = {
    top:    { bottom: '100%', left: '50%', transform: 'translateX(-50%)', marginBottom: '7px' },
    bottom: { top: '100%', left: '50%', transform: 'translateX(-50%)', marginTop: '7px' },
    left:   { right: '100%', top: '50%', transform: 'translateY(-50%)', marginRight: '7px' },
    right:  { left: '100%', top: '50%', transform: 'translateY(-50%)', marginLeft: '7px' },
  }[placement]

  return (
    <span style={{ position: 'relative', display: 'inline-flex', ...style }}
      onMouseEnter={enter} onMouseLeave={leave}>
      {children}
      {show && (
        <span role="tooltip" style={{
          position: 'absolute', zIndex: 50, whiteSpace: 'nowrap', pointerEvents: 'none',
          background: 'var(--bg-mantle)', border: 'var(--border)', borderRadius: 'var(--radius-md)',
          boxShadow: 'var(--shadow-md)', padding: '6px 9px', ...pos,
        }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: 'var(--font-size-sm)', fontWeight: 500, color: 'var(--text-primary)' }}>{label}</span>
            {shortcut && (
              <kbd style={{ fontFamily: 'var(--font-family-mono)', fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)',
                border: 'var(--border)', borderRadius: 'var(--radius-xs)', padding: '0 4px' }}>{shortcut}</kbd>
            )}
          </span>
          {description && (
            <span style={{ display: 'block', marginTop: '3px', maxWidth: '220px', whiteSpace: 'normal',
              fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', lineHeight: 1.4 }}>{description}</span>
          )}
        </span>
      )}
    </span>
  )
}
