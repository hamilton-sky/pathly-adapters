// Single source of truth for rendering timestamps across Studio.
//
// Before this module there were six hand-rolled relative-"ago" formatters plus
// several inconsistent absolute ones, disagreeing on granularity ("3m" vs
// "3 min"), wording, and where the ladder stopped. Everything now flows through
// the pure functions here (and the `<Timestamp>` component that wraps them).
//
// Design decisions (PO + designer consult):
//  • ONE relative ladder, ending deliberately:
//      just now (<45s) → Nm ago → Nh ago → Nd ago (≤6d) → absolute date (≥7d)
//  • The " ago" suffix is owned HERE, never appended at call sites.
//  • Never throw: missing/invalid → sentinel; a bad timestamp must not break a
//    list render. Future timestamps (clock skew) clamp to "just now" within a
//    tolerance, else fall back to the absolute date.
//  • Absolute/clock formatting is locale-aware via Intl with EXPLICIT options —
//    never a bare toLocaleString(), which drifts across OS locales (the very
//    inconsistency being removed here).

export type TimeInput = string | number | Date | null | undefined

/** Rendered for missing/invalid instants on relative + absolute surfaces. */
export const TIME_SENTINEL = '—'
/** Rendered for missing/invalid instants on clock (HH:MM:SS) surfaces. */
export const CLOCK_SENTINEL = '--:--:--'

const MINUTE = 60_000
const HOUR = 3_600_000
const DAY = 86_400_000
/** Clock-skew grace: a timestamp up to this far in the future reads "just now". */
const FUTURE_TOLERANCE_MS = MINUTE
/** Past this age the relative ladder flips to an absolute date. */
const RELATIVE_MAX_MS = 7 * DAY

const dateFmt = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' })
const dateFmtYear = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
// Numeric on purpose — "7/6/2026, 9:46 PM", not "Mon, Jul 6…". Read as an exact
// instant on card faces + tooltips; seconds live in formatClock for dense log rows.
const absoluteFmt = new Intl.DateTimeFormat(undefined, {
  year: 'numeric', month: 'numeric', day: 'numeric',
  hour: 'numeric', minute: '2-digit',
})
const clockFmt = new Intl.DateTimeFormat(undefined, {
  hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
})

/** Normalize any accepted input to epoch ms, or null if missing/invalid. */
function toMs(input: TimeInput): number | null {
  if (input == null) return null
  const ms = input instanceof Date
    ? input.getTime()
    : typeof input === 'number'
      ? input
      : new Date(input).getTime()
  return Number.isNaN(ms) ? null : ms
}

/** ISO-8601 string for the `<time dateTime>` attribute; '' when unknown. */
export function toISO(input: TimeInput): string {
  const ms = toMs(input)
  return ms == null ? '' : new Date(ms).toISOString()
}

/** Compact date, no time — "Jul 6" (current year) or "Jul 6, 2025" (prior year). */
export function formatDateShort(input: TimeInput): string {
  const ms = toMs(input)
  if (ms == null) return TIME_SENTINEL
  const d = new Date(ms)
  return d.getFullYear() === new Date().getFullYear() ? dateFmt.format(d) : dateFmtYear.format(d)
}

/**
 * Local calendar-day key (YYYY-MM-DD) for day-boundary detection — e.g. inserting
 * a date divider in a log when the day changes. null for missing/invalid input.
 */
export function dayKey(input: TimeInput): string | null {
  const ms = toMs(input)
  if (ms == null) return null
  const d = new Date(ms)
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${month}-${day}`
}

/**
 * Relative label with the " ago" suffix owned here. The one canonical ladder:
 * `just now` → `Nm ago` → `Nh ago` → `Nd ago` → flips to an absolute date at 7d.
 */
export function formatRelative(input: TimeInput): string {
  const ms = toMs(input)
  if (ms == null) return TIME_SENTINEL
  const diff = Date.now() - ms
  if (diff < 0) {
    // Future timestamp: tolerate small clock skew, else show the date rather
    // than emit a nonsensical "in 3m".
    return diff > -FUTURE_TOLERANCE_MS ? 'just now' : formatDateShort(ms)
  }
  if (diff < 45_000) return 'just now'
  if (diff < HOUR) return `${Math.floor(diff / MINUTE)}m ago`
  if (diff < DAY) return `${Math.floor(diff / HOUR)}h ago`
  if (diff < RELATIVE_MAX_MS) return `${Math.floor(diff / DAY)}d ago`
  return formatDateShort(ms)
}

/** Full absolute datetime, numeric — "7/6/2026, 9:46 PM". Card faces, tooltips, audit. */
export function formatAbsolute(input: TimeInput): string {
  const ms = toMs(input)
  if (ms == null) return TIME_SENTINEL
  return absoluteFmt.format(new Date(ms))
}

/** Time-of-day HH:MM:SS for dense log rows (event log, run log, output tab). */
export function formatClock(input: TimeInput): string {
  const ms = toMs(input)
  if (ms == null) return CLOCK_SENTINEL
  return clockFmt.format(new Date(ms))
}
