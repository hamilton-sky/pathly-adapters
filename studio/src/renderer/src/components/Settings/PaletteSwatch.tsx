import type { ThemeName } from '../../theme'
import { themes, paletteLabels } from '../../theme'
import s from './PaletteSwatch.module.css'

interface Props {
  name: ThemeName
  active: boolean
  onClick: () => void
}

export function PaletteSwatch({ name, active, onClick }: Props): JSX.Element {
  const p = themes[name]
  return (
    <div
      onClick={onClick}
      className={`${s.wrapper}${active ? ` ${s.active}` : ''}`}
      style={{
        '--swatch-accent': p.accent,
        '--swatch-accent-alpha': `${p.accent}18`,
        '--swatch-bg': p.bgBase,
        '--swatch-terminal': p.bgTerminal,
        '--swatch-green': p.green,
        '--swatch-red': p.red,
        '--swatch-border': p.bgSurface0,
        '--swatch-text': p.textSecondary,
      } as React.CSSProperties}
    >
      <div className={s.preview}>
        <div className={s.topBar}>
          <div className={`${s.dot} ${s.dotAccent}`} />
          <div className={`${s.dot} ${s.dotGreen}`} />
          <div className={`${s.dot} ${s.dotRed}`} />
        </div>
        <div className={s.terminal} />
      </div>
      <span className={`${s.label}${active ? ` ${s.active}` : ''}`}>
        {paletteLabels[name]}
      </span>
    </div>
  )
}
