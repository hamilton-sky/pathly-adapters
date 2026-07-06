import { formatAbsolute, formatClock, formatRelative, toISO, type TimeInput } from '../../utils/timestamp'
import s from './Timestamp.module.css'

export interface TimestampProps {
  /** Any instant — ISO string, epoch ms, or Date. Nullish renders a sentinel. */
  value: TimeInput
  /**
   * - `relative` (default): relative label ("3h ago"), full datetime in the tooltip.
   *   Use on glance surfaces — cards, headers, monitor bar.
   * - `absolute`: full datetime primary, relative in the tooltip.
   * - `clock`: HH:MM:SS primary for dense log rows, full datetime in the tooltip.
   */
  mode?: 'relative' | 'absolute' | 'clock'
  className?: string
}

/**
 * Semantic timestamp: renders a `<time dateTime>` so the machine-readable instant
 * and a hover tooltip ride along with every visible label — the absolute time is
 * always one hover away on relative surfaces, and vice-versa. Styling comes from
 * the caller's `className` (token-based); this owns only wrap behavior.
 */
export function Timestamp({ value, mode = 'relative', className }: TimestampProps): JSX.Element {
  const iso = toISO(value)
  const relative = formatRelative(value)
  const absolute = formatAbsolute(value)
  const primary = mode === 'absolute' ? absolute : mode === 'clock' ? formatClock(value) : relative
  const title = mode === 'relative' ? absolute : relative
  return (
    <time className={className ? `${s.ts} ${className}` : s.ts} title={title} {...(iso ? { dateTime: iso } : {})}>
      {primary}
    </time>
  )
}
