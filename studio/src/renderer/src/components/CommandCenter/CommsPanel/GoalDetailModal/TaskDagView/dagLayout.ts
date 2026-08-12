import type { Message } from '../../../types'

export type DagOrient = 'vertical' | 'horizontal' | 'snake'
export type CommentColor = 'yellow' | 'blue' | 'green' | 'pink' | 'purple'

export interface DagComment {
  id: string
  text: string
  color: CommentColor
  taskIds: string[] // empty = general note; non-empty = attached to these specific tasks
  x: number
  y: number
}

export interface DagNode {
  id: string
  x: number
  y: number
  w: number
  h: number
  index: number
  task: Message
}
interface DagEdge {
  from: string
  to: string
}
export interface DagLayout {
  nodes: DagNode[]
  edges: DagEdge[]
  width: number
  height: number
}

const NODE_W = 150
const NODE_H = 44
const GAP_MAIN = 52 // gap along the depth axis (between layers / rows)
const GAP_CROSS = 22 // gap along the spread axis (within a layer / row)
const PAD = 18

// Layered DAG layout. A task's LAYER is its longest dependency chain (depth); nodes in a layer
// spread along the cross axis. orient: 'vertical' lays layers top→bottom; 'horizontal' left→right;
// 'snake' ignores depth and packs tasks in topological order into a COMPACT serpentine grid (rows
// alternate direction) — ideal for a long linear chain. Edges connect every in-set dependency to
// its task. Cycles are tolerated via a `visiting` guard. Pure + DOM-free → testable.
export function dagLayout(tasks: Message[], order: Message[] = tasks, orient: DagOrient = 'vertical'): DagLayout {
  const byId = new Map(tasks.map((t) => [t.id, t]))
  const inSet = new Set(tasks.map((t) => t.id))
  const indexOf = new Map(order.map((t, i) => [t.id, i]))

  const edges: DagEdge[] = []
  for (const t of tasks) {
    for (const dep of t.dependsOn ?? []) {
      if (inSet.has(dep)) edges.push({ from: dep, to: t.id })
    }
  }

  // ── Snake: pack topological order into a compact serpentine grid ────────────
  if (orient === 'snake') {
    const items = order.filter((t) => inSet.has(t.id))
    const cols = Math.max(1, Math.min(5, Math.ceil(Math.sqrt(items.length))))
    const nodes: DagNode[] = items.map((t, i) => {
      const row = Math.floor(i / cols)
      const c0 = i % cols
      const col = row % 2 === 0 ? c0 : cols - 1 - c0 // reverse every other row → snake
      return {
        id: t.id,
        x: PAD + col * (NODE_W + GAP_CROSS),
        y: PAD + row * (NODE_H + GAP_MAIN),
        w: NODE_W,
        h: NODE_H,
        index: (indexOf.get(t.id) ?? 0) + 1,
        task: t,
      }
    })
    const rows = Math.ceil(items.length / cols)
    return {
      nodes,
      edges,
      width: cols * NODE_W + (cols - 1) * GAP_CROSS + PAD * 2,
      height: Math.max(rows * NODE_H + Math.max(rows - 1, 0) * GAP_MAIN + PAD * 2, NODE_H + PAD * 2),
    }
  }

  // ── Tree (vertical / horizontal): layer by dependency depth ─────────────────
  const depthCache = new Map<string, number>()
  const visiting = new Set<string>()
  function depth(t: Message): number {
    const cached = depthCache.get(t.id)
    if (cached !== undefined) return cached
    if (visiting.has(t.id)) return 0
    visiting.add(t.id)
    let d = 0
    for (const dep of t.dependsOn ?? []) {
      const parent = byId.get(dep)
      if (parent) d = Math.max(d, depth(parent) + 1)
    }
    visiting.delete(t.id)
    depthCache.set(t.id, d)
    return d
  }

  const layers = new Map<number, Message[]>()
  order.forEach((t) => {
    if (!inSet.has(t.id)) return
    const d = depth(t)
    const layer = layers.get(d) ?? []
    layer.push(t)
    layers.set(d, layer)
  })

  const horiz = orient === 'horizontal'
  const mainNode = horiz ? NODE_W : NODE_H
  const crossNode = horiz ? NODE_H : NODE_W
  const depths = [...layers.keys()].sort((a, b) => a - b)
  const nodes: DagNode[] = []
  let maxCross = 0
  depths.forEach((d, layerIdx) => {
    const layer = layers.get(d) ?? []
    maxCross = Math.max(maxCross, layer.length * crossNode + (layer.length - 1) * GAP_CROSS)
    layer.forEach((t, i) => {
      const main = PAD + layerIdx * (mainNode + GAP_MAIN)
      const cross = PAD + i * (crossNode + GAP_CROSS)
      nodes.push({
        id: t.id,
        x: horiz ? main : cross,
        y: horiz ? cross : main,
        w: NODE_W,
        h: NODE_H,
        index: (indexOf.get(t.id) ?? 0) + 1,
        task: t,
      })
    })
  })

  const rows = depths.length
  const mainExtent = rows * mainNode + Math.max(rows - 1, 0) * GAP_MAIN
  return {
    nodes,
    edges,
    width: Math.max((horiz ? mainExtent : maxCross) + PAD * 2, NODE_W + PAD * 2),
    height: Math.max((horiz ? maxCross : mainExtent) + PAD * 2, NODE_H + PAD * 2),
  }
}
