import { useStore } from '../../../store'
import type { ThemeName } from '../../../theme'
import { paletteLabels } from '../../../theme'
import { PaletteSwatch } from '../PaletteSwatch'
import s from '../Settings.module.css'

const DARK_PALETTES: ThemeName[] = ['dark', 'nord', 'mocha', 'solarized', 'dracula', 'rose-pine']
const LIGHT_PALETTES: ThemeName[] = ['light', 'solarized-light', 'latte', 'paper', 'rose-pine-dawn', 'mint']

export function AppearanceSettings(): JSX.Element {
  const { preferredDark, preferredLight, setPreferredDark, setPreferredLight } = useStore()

  return (
    <div className={s.section}>
      <div className={s.sectionTitle}>Color Palette</div>
      <div className={s.hint}>
        Select your preferred <strong>dark</strong> and <strong>light</strong> palette. The ☽/☀ toggle switches between them.
      </div>
      <div className={s.paletteGroupLabel}>
        Dark — <span className={s.accentText}>{paletteLabels[preferredDark]}</span>
      </div>
      <div data-testid="settings-palette-dark-swatches" className={s.swatchRowSpaced}>
        {DARK_PALETTES.map((name) => (
          <PaletteSwatch key={name} data-testid={`settings-palette-${name.replace(/\s+/g, '-').toLowerCase()}`} name={name} active={preferredDark === name} onClick={() => setPreferredDark(name)} />
        ))}
      </div>
      <div className={s.paletteGroupLabelBottom}>
        Light — <span className={s.accentText}>{paletteLabels[preferredLight]}</span>
      </div>
      <div data-testid="settings-palette-light-swatches" className={s.swatchRow}>
        {LIGHT_PALETTES.map((name) => (
          <PaletteSwatch key={name} data-testid={`settings-palette-${name.replace(/\s+/g, '-').toLowerCase()}`} name={name} active={preferredLight === name} onClick={() => setPreferredLight(name)} />
        ))}
      </div>
    </div>
  )
}
