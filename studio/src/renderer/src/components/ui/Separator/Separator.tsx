import { useTheme } from '../../useTheme'

interface SeparatorProps {
  label?: string
}

export function Separator({ label }: SeparatorProps): JSX.Element {
  const t = useTheme()

  const lineStyle: React.CSSProperties = {
    flex: 1,
    height: '1px',
    background: t.bgSurface1,
  }

  if (!label) {
    return <div style={{ ...lineStyle, flex: 'none', width: '100%', margin: '6px 0' }} />
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 12px' }}>
      <div style={lineStyle} />
      <span style={{ color: t.textMuted, fontSize: '10px', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>
        {label}
      </span>
      <div style={lineStyle} />
    </div>
  )
}
