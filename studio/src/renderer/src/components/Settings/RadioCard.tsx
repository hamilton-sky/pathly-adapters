import { useTheme } from '../../useTheme'
import { makeStyles } from './Settings.styles'

interface Props {
  active: boolean
  label: string
  description: string
  onClick: () => void
}

export function RadioCard({ active, label, description, onClick }: Props): JSX.Element {
  const s = makeStyles(useTheme())
  return (
    <div style={s.radioCard(active)} onClick={onClick}>
      <span style={s.radioLabel(active)}>
        <span>{active ? '●' : '○'}</span> {label}
      </span>
      <span style={s.radioDesc}>{description}</span>
    </div>
  )
}
