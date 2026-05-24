import type { ThemeName } from '../../theme'
import { paletteLabels } from '../../theme'
import { makeSwatchStyles } from './Settings.styles'

interface Props {
  name: ThemeName
  active: boolean
  onClick: () => void
}

export function PaletteSwatch({ name, active, onClick }: Props): JSX.Element {
  const s = makeSwatchStyles(name, active)
  return (
    <div onClick={onClick} style={s.wrapper}>
      <div style={s.preview}>
        <div style={s.topBar}>
          <div style={s.dotAccent} />
          <div style={s.dotGreen} />
          <div style={s.dotRed} />
        </div>
        <div style={s.terminal} />
      </div>
      <span style={s.label}>{paletteLabels[name]}</span>
    </div>
  )
}
