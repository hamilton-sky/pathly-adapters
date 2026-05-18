import { useTheme } from '../../useTheme'

interface BadgeProps {
  label: string
  color?: string
  style?: React.CSSProperties
}

export function Badge({ label, color, style }: BadgeProps): JSX.Element {
  const t = useTheme()

  const baseStyle: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    padding: '1px 6px',
    borderRadius: '4px',
    fontFamily: 'monospace',
    fontSize: '11px',
    color: color ?? t.textMuted,
    border: `1px solid ${color ?? t.textMuted}44`,
    background: (color ?? t.textMuted) + '18',
    ...style,
  }

  return <span style={baseStyle}>{label}</span>
}
