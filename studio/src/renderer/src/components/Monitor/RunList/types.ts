// RunSummary — one row from GET /runs (unified-control-plane P0, list_runs + the live-status
// overlay). One entry per TOP-LEVEL run (a flow's per-stage spawns are folded out), unlike the
// live engine board which shows one card per spawn.

export interface RunSummary {
  run_id: string
  /** flow | single | loop | decompose. */
  kind: string
  feature: string
  board_scope: string | null
  status: string
  adapter: string | null
  started_at: string | null
  finished_at: string | null
  stage_count: number | null
  cost_usd: number
  tokens_total: number
  /** Per-kind capability hints from the dispatch overlay (display-only in P0). */
  capabilities?: string[]
}
