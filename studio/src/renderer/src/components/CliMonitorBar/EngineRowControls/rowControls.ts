import type { EngineCategory, EngineStatus } from '../types'

/** One row control. `kind` drives styling; `id` is the action dispatched to the host. */
export interface RowControl {
  id: string
  icon: string   // unicode glyph — swap for a lucide icon in the component if preferred
  title: string
  kind: 'default' | 'danger'
}

// Per-engine controls, derived from status. Same policy as the full Monitor's controlsForEngine:
// only verbs the runtime honors — open / stop when running, move-up / cancel when queued.
// Pause/reroute aren't wired yet, so the dock doesn't show them. `_category` is kept for signature
// parity with the board (controlsForEngine) and future per-category verbs.
export function rowControls(status: EngineStatus, _category: EngineCategory): RowControl[] {
  if (status === 'queued') {
    return [
      { id: 'up',     icon: '↑', title: 'Move up', kind: 'default' },
      { id: 'cancel', icon: '✕', title: 'Cancel',  kind: 'danger' },
    ]
  }
  return [
    { id: 'open', icon: '↗', title: 'Open terminal', kind: 'default' },
    { id: 'stop', icon: '■', title: 'Stop',          kind: 'danger' },
  ]
}
