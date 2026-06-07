import React from 'react'

/**
 * Pathly Spinner — small rotating ring. Inherits currentColor by default.
 */
export function Spinner({ size = 14, color = 'var(--accent)', strokeWidth = 2, style }) {
  return (
    <span
      className="pathly-spinner"
      style={{
        display: 'inline-block', width: `${size}px`, height: `${size}px`,
        borderRadius: '50%', border: `${strokeWidth}px solid var(--bg-surface1)`,
        borderTopColor: color, animation: 'pathly-spin 0.7s linear infinite', ...style,
      }}
    >
      <style>{'@keyframes pathly-spin{to{transform:rotate(360deg)}}'}</style>
    </span>
  )
}
