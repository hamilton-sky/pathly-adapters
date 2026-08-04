// RunDetail — the GET /runs/<id> payload shape (unified-control-plane P0, ARCHITECTURE §4.2).
// Mirrors db/queries/run_history_read.get_run_detail. The read-model is the source of truth, so
// every field is treated as possibly-null at the boundary.

export interface RunDetailRun {
  run_id: string
  project_root: string
  feature: string
  board_scope: string | null
  status: string
  adapter: string | null
  /** flow | single | loop | decompose (stage rows are folded out of the list). */
  kind: string
  started_at: string | null
  finished_at: string | null
  stage_count: number | null
  cost_usd: number
  tokens_total: number
}

export interface RunDetailStage {
  run_id: string
  stage: string | null
  adapter: string | null
  status: string
  started_at: string | null
  finished_at: string | null
  cost_usd: number
  tokens: number
}

export interface RunDetailLog {
  stage: string | null
  prompt_sent: string | null
  /** Discrete in P1; embedded in prompt_sent (NULL) in P0. */
  board_context_injected: string | null
  stdin: string | null
  stdout: string | null
  ts: string | null
}

export interface RunDetailBoardPost {
  id: string
  from_agent: string | null
  type: string | null
  text: string | null
  ts: string | null
  run_id: string | null
}

export interface RunDetailArtifact {
  path: string | null
  type: string | null
  title: string | null
  summary: string | null
}

export interface RunDetailCost {
  cost_usd: number
  tokens_total: number
  invocations: number
}

export interface RunDetail {
  /** null when the run_id is unknown (the route 404s; the page shows a not-found state). */
  run: RunDetailRun | null
  stages: RunDetailStage[]
  logs: RunDetailLog[]
  board: RunDetailBoardPost[]
  artifacts: RunDetailArtifact[]
  cost: RunDetailCost
}
