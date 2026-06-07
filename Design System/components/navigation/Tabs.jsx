import React from 'react'

/**
 * Pathly Tabs — horizontal tab bar. Two looks:
 *  - "underline" (default): in-panel tabs (Timeline · Events · Agents · SQL)
 *  - "pill": top-level view switch (active = accent-tinted pill)
 * Each tab is { id, label, count? }.
 */
export function Tabs({ tabs = [], activeId, onChange, variant = 'underline', style }) {
  const isPill = variant === 'pill'

  const bar = {
    display: 'flex', alignItems: 'center',
    gap: isPill ? '4px' : '20px',
    borderBottom: isPill ? 'none' : 'var(--border)',
    ...style,
  }

  return (
    <div className="pathly-tabs" style={bar}>
      {tabs.map((t) => {
        const active = t.id === activeId
        const tabStyle = isPill
          ? {
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '5px 11px', borderRadius: 'var(--radius-md)', cursor: 'pointer',
              border: 'none', background: active ? 'var(--accent-bg)' : 'transparent',
              color: active ? 'var(--accent)' : 'var(--text-secondary)',
              fontFamily: 'var(--font-family-base)', fontSize: 'var(--font-size-base)',
              fontWeight: 500, transition: 'background var(--transition-fast), color var(--transition-fast)',
            }
          : {
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '0 0 9px', marginBottom: '-1px', cursor: 'pointer',
              border: 'none', borderBottom: `2px solid ${active ? 'var(--accent)' : 'transparent'}`,
              background: 'transparent',
              color: active ? 'var(--text-primary)' : 'var(--text-muted)',
              fontFamily: 'var(--font-family-base)', fontSize: 'var(--font-size-base)',
              fontWeight: active ? 600 : 500, transition: 'color var(--transition-fast)',
            }
        return (
          <button key={t.id} type="button" className="pathly-tab" data-active={active ? 'true' : undefined}
            style={tabStyle} onClick={() => onChange && onChange(t.id)}>
            {t.label}
            {t.count != null && (
              <span style={{
                fontFamily: 'var(--font-family-mono)', fontSize: 'var(--font-size-xs)',
                padding: '1px 5px', borderRadius: 'var(--radius-full)', lineHeight: 1.4,
                background: active ? 'var(--accent-bg)' : 'var(--bg-surface1)',
                color: active ? 'var(--accent)' : 'var(--text-muted)',
              }}>{t.count}</span>
            )}
          </button>
        )
      })}
    </div>
  )
}
