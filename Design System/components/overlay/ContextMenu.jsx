import React from 'react'

/**
 * Pathly ContextMenu — floating menu surface of action rows. Each item is
 * { label, icon?, onClick?, danger?, shortcut? } or { separator: true }.
 * Renders the menu panel itself; pair with your own trigger/positioning.
 */
export function ContextMenu({ items = [], style }) {
  return (
    <div className="pathly-context-menu" role="menu" style={{
      minWidth: '180px', padding: '4px',
      background: 'var(--bg-mantle)', border: 'var(--border)',
      borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-lg)', ...style,
    }}>
      {items.map((it, i) => {
        if (it.separator) {
          return <div key={i} style={{ height: '1px', background: 'var(--border-color)', margin: '4px 0' }} />
        }
        return <MenuRow key={i} item={it} />
      })}
    </div>
  )
}

function MenuRow({ item }) {
  const [hover, setHover] = React.useState(false)
  const color = item.danger ? 'var(--red)' : (hover ? 'var(--accent)' : 'var(--text-primary)')
  return (
    <button type="button" role="menuitem" onClick={item.onClick}
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: '9px', width: '100%',
        padding: '7px 10px', border: 'none', borderRadius: 'var(--radius-sm)',
        background: hover ? (item.danger ? 'var(--red-bg)' : 'var(--bg-surface1)') : 'transparent',
        color, cursor: 'pointer', textAlign: 'left',
        fontFamily: 'var(--font-family-base)', fontSize: 'var(--font-size-base)',
        transition: 'background var(--transition-fast), color var(--transition-fast)',
      }}>
      {item.icon && <span style={{ display: 'inline-flex', flexShrink: 0 }}>{item.icon}</span>}
      <span style={{ flex: 1 }}>{item.label}</span>
      {item.shortcut && (
        <kbd style={{ fontFamily: 'var(--font-family-mono)', fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)' }}>{item.shortcut}</kbd>
      )}
    </button>
  )
}
