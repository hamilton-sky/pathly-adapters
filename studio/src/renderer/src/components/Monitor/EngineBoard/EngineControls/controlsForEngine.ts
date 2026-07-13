import type { EngineCategory, EngineStatus } from '../types'

/** A single control action available on an engine. `kind` drives the button style. */
export interface EngineControl {
  id: string
  label: string
  kind: 'default' | 'danger'
}

// Contextual controls, derived from the engine's category + status. Every verb here is wired to a
// real handler in the Pipeline panel (Monitor/index.tsx) — we deliberately don't surface actions
// the runtime can't yet honor (pause/reroute/rerun), so no button is a no-op.
//   queued      → move up / cancel   (spawn-queue reorder + cancel)
//   flow        → open / configure / abort
//   loop|single → open / stop
//   done|failed → open
export function controlsForEngine(status: EngineStatus, category: EngineCategory): EngineControl[] {
  if (status === 'queued') {
    return [
      { id: 'up',     label: 'Move up', kind: 'default' },
      { id: 'cancel', label: 'Cancel',  kind: 'danger' },
    ]
  }
  if (status === 'done' || status === 'failed') {
    return [{ id: 'open', label: 'Open terminal', kind: 'default' }]
  }
  if (category === 'flow') {
    return [
      { id: 'open',      label: 'Open terminal',   kind: 'default' },
      { id: 'configure', label: 'Configure stage', kind: 'default' },
      { id: 'abort',     label: 'Abort',           kind: 'danger' },
    ]
  }
  // loop + single
  return [
    { id: 'open', label: 'Open terminal', kind: 'default' },
    { id: 'stop', label: 'Stop',          kind: 'danger' },
  ]
}
