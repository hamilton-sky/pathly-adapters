import { describe, it, expect } from 'vitest'
import { borderPoint, edgePath, type Rect } from './edgePath'

// Standard DAG node box (see NODE_W/NODE_H in dagLayout).
const box = (x: number, y: number): Rect => ({ x, y, w: 150, h: 44 })

// Pull the first and last "x,y" pairs out of a path string: the start anchor and the
// marker-end (arrowhead) anchor. Both must sit on their respective node borders.
function coords(d: string): { start: { x: number; y: number }; end: { x: number; y: number } } {
  const n = d.match(/-?\d+(?:\.\d+)?/g)!.map(Number)
  return { start: { x: n[0], y: n[1] }, end: { x: n[n.length - 2], y: n[n.length - 1] } }
}

const onBorder = (p: { x: number; y: number }, r: Rect): boolean =>
  p.x === r.x || p.x === r.x + r.w || p.y === r.y || p.y === r.y + r.h

describe('borderPoint', () => {
  it('returns top-centre for a source directly above', () => {
    expect(borderPoint({ x: 75, y: 0 }, box(0, 100))).toEqual({ x: 75, y: 100 })
  })
  it('returns left-centre for a source directly to the left', () => {
    expect(borderPoint({ x: 0, y: 22 }, box(100, 0))).toEqual({ x: 100, y: 22 })
  })
  it('lands on the rect border for a diagonal source', () => {
    const rect = box(300, 300)
    expect(onBorder(borderPoint({ x: 75, y: 22 }, rect), rect)).toBe(true)
  })
})

describe('edgePath', () => {
  it('is a straight line, never a bezier', () => {
    const d = edgePath(box(0, 0), box(0, 100))
    expect(d).toContain(' L')
    expect(d).not.toContain(' C')
  })

  it('vertical stack: source bottom border → target top border', () => {
    const { start, end } = coords(edgePath(box(0, 0), box(0, 100)))
    expect(start).toEqual({ x: 75, y: 44 })  // a bottom-centre
    expect(end).toEqual({ x: 75, y: 100 })   // b top-centre (arrowhead)
  })

  it('horizontal: source right border → target left border', () => {
    const { start, end } = coords(edgePath(box(0, 0), box(200, 0)))
    expect(start).toEqual({ x: 150, y: 22 }) // a right-centre
    expect(end).toEqual({ x: 200, y: 22 })   // b left-centre (arrowhead)
  })

  it('diagonal: both endpoints sit on their box borders', () => {
    const a = box(0, 0)
    const b = box(300, 300)
    const { start, end } = coords(edgePath(a, b))
    expect(onBorder(start, a)).toBe(true)
    expect(onBorder(end, b)).toBe(true)
  })
})
