import { formatAbsolute } from '../../../../utils/timestamp'

// Full timestamp for the tile tooltip + hover preview — routed through the shared
// timestamp util (never hand-rolled). Empty string (not the '—' sentinel) for a
// missing ts so the tile simply carries no tooltip. The tile face keeps the short
// relative time from <Timestamp> so the grid stays scannable.
export function absoluteTime(ts?: string | null): string {
  return ts ? formatAbsolute(ts) : ''
}

export function firstLine(text: string): string {
  return text.split('\n').find((l) => l.trim()) ?? text
}
