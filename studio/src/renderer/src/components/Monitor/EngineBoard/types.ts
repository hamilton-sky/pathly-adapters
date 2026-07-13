// Monitor — domain & UI types
// The Monitor treats every spawned CLI engine as a card, grouped by *how* it runs.
// Field names align with the runner/terminal telemetry surfaced to the renderer.

/** How the engine was spawned — the primary board grouping. */
export type EngineCategory = 'flow' | 'loop' | 'single'

/** Which host CLI is driving the engine. */
export type EngineAdapter = 'Claude' | 'Codex' | 'Gemini'

/** What the engine is doing in its pipeline. Mirrors the FSM stages plus the
 *  one-shot roles that single/loop engines carry. */
export type EngineRole =
  | 'planner' | 'builder' | 'reviewer' | 'tester' | 'retro'   // flow stages
  | 'evaluate' | 'analyze' | 'split' | 'send-comments'         // single / loop actions

/** FSM stage — set on flow (and some loop) engines; empty for single shots. */
export type Stage =
  | 'STORMING' | 'PLANNING' | 'BUILDING' | 'REVIEWING' | 'TESTING' | 'RETRO' | 'DONE'
  | '' // single shots have no stage

export type EngineStatus = 'running' | 'queued' | 'done' | 'failed'

export interface MonitorEngine {
  /** Stable id — maps to the runner tabId / spawn id. */
  id: string
  adapter: EngineAdapter
  category: EngineCategory
  role: EngineRole
  /** Feature / target the engine is working on (mono display). */
  feature: string
  /** FSM stage label, or a loop marker like "cycle 3"; '' for single shots. */
  stage: Stage | string
  status: EngineStatus
  /** Human elapsed, e.g. "4m 12s"; '-' when queued. */
  elapsed: string
  /** Start timestamp, e.g. "14:28:41"; '-' when queued. */
  started: string
  /** Token counts (mono). */
  tokensIn: string
  tokensOut: string
  /** Combined token label, e.g. "128.4k tok". */
  tokens: string
  /** Dollar cost, e.g. "$2.10"; '-' when queued. */
  cost: string
  /** Latest live output line. */
  snippet: string
}
