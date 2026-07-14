// Pure, side-effect-free math + formatting helpers for the chart.
import type { ScaleMode } from './types'

export function fmtCost(n: number): string {
  return n > 0 && n < 0.01 ? `$${n.toFixed(4)}` : `$${n.toFixed(2)}`
}

export function fmtTokens(n: number): string {
  return n >= 1000 ? `${Math.round(n / 1000)}k` : String(n)
}

/** "2026-06-22" -> "06/22"; passes through anything already short. */
export function fmtDay(day: string): string {
  return day.length >= 10 ? day.slice(5).replace('-', '/') : day
}

/** Bar height as a 0..1 fraction of the plot, honouring the scale mode. */
export function heightFrac(cost: number, max: number, scale: ScaleMode): number {
  if (cost <= 0) return 0
  return scale === 'log' ? Math.log1p(cost) / Math.log1p(max) : cost / max
}

/** Inverse of heightFrac — the $ value a gridline at `frac` represents. */
export function gridValue(frac: number, max: number, scale: ScaleMode): number {
  return scale === 'log' ? Math.expm1(frac * Math.log1p(max)) : max * frac
}
