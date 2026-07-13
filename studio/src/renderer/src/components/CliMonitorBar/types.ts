// CliMonitorBar — domain & UI types
// The floating dock reuses the Monitor's engine model. Keep this in sync with
// ../Monitor/types.ts (or import from there once both live in the tree).

export type EngineCategory = 'flow' | 'loop' | 'single'
export type EngineAdapter = 'Claude' | 'Codex' | 'Gemini'
export type EngineStatus = 'running' | 'queued' | 'done' | 'failed'

export type EngineRole =
  | 'planner' | 'builder' | 'reviewer' | 'tester' | 'retro'
  | 'evaluate' | 'analyze' | 'split' | 'send-comments'

export type Stage =
  | 'STORMING' | 'PLANNING' | 'BUILDING' | 'REVIEWING' | 'TESTING' | 'RETRO' | 'DONE' | ''

/** Compact engine shape the dock renders. Subset of Monitor's MonitorEngine. */
export interface DockEngine {
  id: string
  adapter: EngineAdapter
  category: EngineCategory
  role: EngineRole
  feature: string
  stage: Stage | string
  status: EngineStatus
  /** Human elapsed, "4m 12s"; '-' when queued. */
  elapsed: string
  /** One-line current activity, e.g. "Edit /lib/auth.ts". */
  sub: string
}

/** 'all' plus the three categories — the mini filter value. */
export type DockCategoryFilter = 'all' | EngineCategory
