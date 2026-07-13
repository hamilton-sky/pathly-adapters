// Pure edge geometry for the task DAG — DOM-free so it can be unit-tested (mirrors dagLayout).

export interface Pt { x: number; y: number }
export interface Rect { x: number; y: number; w: number; h: number }

// Point where the ray from `from` to the rect's centre crosses the rect's border — so an
// arrowhead lands ON the target box instead of buried at its (node-covered) centre.
export function borderPoint(from: Pt, rect: Rect): Pt {
  const cx = rect.x + rect.w / 2
  const cy = rect.y + rect.h / 2
  const dx = from.x - cx
  const dy = from.y - cy
  if (dx === 0 && dy === 0) return { x: cx, y: cy }
  const tx = dx === 0 ? Infinity : rect.w / 2 / Math.abs(dx)
  const ty = dy === 0 ? Infinity : rect.h / 2 / Math.abs(dy)
  const t = Math.min(tx, ty)
  return { x: cx + dx * t, y: cy + dy * t }
}

// A dependency connector: a straight line along the centre-to-centre axis, trimmed to each
// box's border so it runs cleanly edge-to-edge and the marker-end arrowhead lands ON the
// target's border (not buried at its node-covered centre). Orientation-independent.
export function edgePath(a: Rect, b: Rect): string {
  const ca = { x: a.x + a.w / 2, y: a.y + a.h / 2 }
  const cb = { x: b.x + b.w / 2, y: b.y + b.h / 2 }
  const start = borderPoint(cb, a)
  const end = borderPoint(ca, b)
  return `M${start.x},${start.y} L${end.x},${end.y}`
}
