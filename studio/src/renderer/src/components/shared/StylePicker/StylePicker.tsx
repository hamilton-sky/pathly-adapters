import type { SummaryStyle } from '../../../store/commsApi'
import s from './StylePicker.module.css'

// Summary DEPTH options — gist (precision) → topic-map (balanced) → detailed (recall).
export const STYLE_OPTIONS: { value: SummaryStyle; label: string; hint: string }[] = [
  { value: 'gist', label: 'Gist', hint: 'One sentence — the core point (precision)' },
  { value: 'topic-map', label: 'Topic map', hint: 'One line per section (balanced)' },
  { value: 'detailed', label: 'Detailed', hint: 'Section + key points (recall)' },
]

interface Props {
  value: SummaryStyle
  onChange: (style: SummaryStyle) => void
  ariaLabel?: string
}

/**
 * Segmented gist / topic-map / detailed depth control. Fills its container (each option
 * flexes equally). Shared by the Artifacts toolbar and the per-artifact Re-summarize
 * popover so the depth options can't drift apart.
 */
export function StylePicker({ value, onChange, ariaLabel = 'Summary depth' }: Props): JSX.Element {
  return (
    <div className={s.row} role="group" aria-label={ariaLabel}>
      {STYLE_OPTIONS.map((opt) => (
        <button
          key={opt.value}
          type="button"
          className={s.btn}
          {...(value === opt.value ? { 'data-active': '' } : {})}
          onClick={() => onChange(opt.value)}
          title={opt.hint}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}
