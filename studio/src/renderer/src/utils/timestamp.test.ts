import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  CLOCK_SENTINEL,
  TIME_SENTINEL,
  formatAbsolute,
  formatClock,
  formatDateShort,
  formatRelative,
  toISO,
} from './timestamp'

// Pin "now" so the relative ladder is deterministic.
const NOW = new Date('2026-07-06T14:03:22.000Z').getTime()

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(NOW)
})
afterEach(() => {
  vi.useRealTimers()
})

const ago = (ms: number): number => NOW - ms
const SEC = 1000
const MIN = 60_000
const HR = 3_600_000
const DAY = 86_400_000

describe('formatRelative — the one canonical ladder', () => {
  it('renders "just now" under 45s', () => {
    expect(formatRelative(ago(0))).toBe('just now')
    expect(formatRelative(ago(44 * SEC))).toBe('just now')
  })
  it('renders minutes, then hours, then days', () => {
    expect(formatRelative(ago(3 * MIN))).toBe('3m ago')
    expect(formatRelative(ago(59 * MIN))).toBe('59m ago')
    expect(formatRelative(ago(3 * HR))).toBe('3h ago')
    expect(formatRelative(ago(23 * HR))).toBe('23h ago')
    expect(formatRelative(ago(3 * DAY))).toBe('3d ago')
    expect(formatRelative(ago(6 * DAY))).toBe('6d ago')
  })
  it('flips to an absolute date at 7 days (PO ladder — no weeks rung)', () => {
    expect(formatRelative(ago(7 * DAY))).not.toMatch(/ago/)
    expect(formatRelative(ago(7 * DAY))).toMatch(/[A-Z][a-z]{2}/) // "Jun 29" etc.
  })
  it('owns its own " ago" suffix', () => {
    // Guards the smell we removed: call sites must never append " ago".
    expect(formatRelative(ago(5 * MIN)).endsWith(' ago')).toBe(true)
  })
})

describe('formatRelative — never throws, handles bad input', () => {
  it('returns the sentinel for null/undefined/invalid, never "NaN ago"', () => {
    expect(formatRelative(null)).toBe(TIME_SENTINEL)
    expect(formatRelative(undefined)).toBe(TIME_SENTINEL)
    expect(formatRelative('not a date')).toBe(TIME_SENTINEL)
    expect(formatRelative('')).toBe(TIME_SENTINEL)
  })
  it('clamps small future skew to "just now", larger to a date — never "in 3m"', () => {
    expect(formatRelative(NOW + 30 * SEC)).toBe('just now')
    expect(formatRelative(NOW + 10 * DAY)).not.toMatch(/ago|in /)
  })
})

describe('input types', () => {
  it('accepts ISO string, epoch number, and Date', () => {
    expect(formatRelative(new Date(ago(3 * MIN)).toISOString())).toBe('3m ago')
    expect(formatRelative(ago(3 * MIN))).toBe('3m ago')
    expect(formatRelative(new Date(ago(3 * MIN)))).toBe('3m ago')
  })
})

describe('formatClock / formatAbsolute / formatDateShort / toISO', () => {
  it('formatClock returns HH:MM:SS and a sentinel for missing', () => {
    expect(formatClock(NOW)).toMatch(/^\d{2}:\d{2}:\d{2}$/)
    expect(formatClock(null)).toBe(CLOCK_SENTINEL)
    expect(formatClock('bad')).toBe(CLOCK_SENTINEL)
  })
  it('formatAbsolute includes year + time, sentinel for missing', () => {
    expect(formatAbsolute(NOW)).toMatch(/2026/)
    expect(formatAbsolute(null)).toBe(TIME_SENTINEL)
  })
  it('formatDateShort omits the current year, sentinel for missing', () => {
    expect(formatDateShort(NOW)).not.toMatch(/2026/)
    expect(formatDateShort(null)).toBe(TIME_SENTINEL)
  })
  it('toISO round-trips a valid instant and is empty for missing', () => {
    expect(toISO(NOW)).toBe(new Date(NOW).toISOString())
    expect(toISO(null)).toBe('')
    expect(toISO('bad')).toBe('')
  })
})
