// Goal DAG runs — decompose a goal into tasks, start/stop the executor, read back progress.

import { apiFetch } from '../../lib/config'


interface RunGoalResult {
  ok: true
  run_id: string
  executor: string
}

interface RunGoalBusy {
  ok: false
  error: 'board_busy'
  reason?: string
}

interface RunGoalTeamUnavailable {
  ok: false
  error: 'not_implemented'
}

export type RunGoalResponse = RunGoalResult | RunGoalBusy | RunGoalTeamUnavailable

export interface RunGoalOpts {
  adapter?: string
  model?: string
  flow?: string
  projectRoot?: string
  /** Per-run board-updates verbosity override; '' / undefined = inherit the Settings default. */
  progress?: string
  /** A Sections-assembled prompt sent verbatim (the 'single' executor's drain-dag run). */
  promptOverride?: string
  /** Transient, per-run, per-stage prompt overrides from the flow gate (FlowGatePreview) —
   *  the 'team' executor's FSM flow, keyed by FSM state. Sent as `stage_overrides` only when
   *  non-empty; single/loop ignore it (they use promptOverride). */
  stageOverrides?: Record<string, string>
}

export type DecomposeMode = 'planner' | 'plan' | 'consultation'

// Decompose a goal into a task DAG. Three tiers, all terminating in the same planner agent:
//   planner      = Quick — bare task list, no artifacts/context_refs
//   plan         = one planner runs planning/plan → full plan + context_refs/depends_on DAG
//   consultation = deep — PO→arch→research→design, then the same planner
// Returns the parsed {ok, reason} so the caller can distinguish board_busy / already_decomposed.
export async function apiDecomposeGoal(
  goal_id: string,
  mode: DecomposeMode,
  opts: { adapter?: string; projectRoot?: string; model?: string; progress?: string; abilityIds?: string[]; promptOverride?: string; stageOverrides?: Record<string, string> } = {},
): Promise<{ ok: boolean; reason?: string } | null> {
  try {
    const body: Record<string, unknown> = { goal_id, mode }
    if (opts.adapter) body.adapter = opts.adapter
    if (opts.projectRoot) body.project_root = opts.projectRoot
    if (opts.model) body.model = opts.model
    if (opts.progress) body.progress = opts.progress
    // Layer-3 abilities compose into the planner prompt; a Sections trim is sent verbatim.
    if (opts.abilityIds?.length) body.ability_ids = opts.abilityIds
    if (opts.promptOverride) body.prompt_override = opts.promptOverride
    // Transient per-stage trims from the flow gate (FlowGatePreview) — mode='consultation' only.
    if (opts.stageOverrides && Object.keys(opts.stageOverrides).length) {
      body.stage_overrides = opts.stageOverrides
    }
    const r = await apiFetch('/comms/goals/decompose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const json = (await r.json().catch(() => null)) as { ok?: boolean; reason?: string } | null
    if (json && typeof json.ok === 'boolean') return { ok: json.ok, reason: json.reason }
    return { ok: r.ok }
  } catch {
    return null
  }
}

export async function apiRunGoal(
  goal_id: string,
  executor?: string,
  opts: RunGoalOpts = {},
): Promise<RunGoalResponse | null> {
  try {
    const body: Record<string, unknown> = { goal_id }
    if (executor) body.executor = executor
    if (opts.adapter) body.adapter = opts.adapter
    if (opts.model) body.model = opts.model
    if (opts.flow) body.flow = opts.flow
    if (opts.projectRoot) body.project_root = opts.projectRoot
    if (opts.progress) body.progress = opts.progress
    if (opts.promptOverride) body.prompt_override = opts.promptOverride
    if (opts.stageOverrides && Object.keys(opts.stageOverrides).length) {
      body.stage_overrides = opts.stageOverrides
    }
    const r = await apiFetch('/comms/goals/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (r.status === 409) {
      return { ok: false, error: 'board_busy' }
    }
    if (r.status === 501) {
      return { ok: false, error: 'not_implemented' }
    }
    return await r.json() as RunGoalResponse
  } catch {
    return null
  }
}

// Run ONE task headlessly (claim → build → complete). The task's status flips to
// in_progress/done via the board feed, so callers don't track a separate run state.
export async function apiRunTask(
  taskId: string,
  opts: { projectRoot?: string; adapter?: string; abilityIds?: string[]; promptOverride?: string } = {},
): Promise<{ ok: boolean; reason?: string; run_id?: string } | null> {
  try {
    const body: Record<string, unknown> = { message_id: taskId }
    if (opts.projectRoot) body.project_root = opts.projectRoot
    if (opts.adapter) body.adapter = opts.adapter
    // Layer-3 abilities compose into the build prompt; a Sections trim is sent verbatim.
    if (opts.abilityIds?.length) body.ability_ids = opts.abilityIds
    if (opts.promptOverride) body.prompt_override = opts.promptOverride
    const r = await apiFetch('/comms/tasks/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    return await r.json() as { ok: boolean; reason?: string; run_id?: string }
  } catch {
    return null
  }
}

// Decompose a whole FEATURE into sibling goals (POST /comms/features/decompose).
// rigor: light → planning/feature-decompose skill · full → planner · consultation → FSM flow.
export async function apiDecomposeFeature(
  feature: string,
  rigor: 'light' | 'full' | 'consultation',
  opts: { projectRoot?: string; adapter?: string; stageOverrides?: Record<string, string> } = {},
): Promise<{ ok: boolean; reason?: string; run_id?: string } | null> {
  try {
    const body: Record<string, unknown> = { feature, rigor }
    if (opts.projectRoot) body.project_root = opts.projectRoot
    if (opts.adapter) body.adapter = opts.adapter
    // Transient per-stage trims from the flow gate (FlowGatePreview) — rigor='consultation' only.
    if (opts.stageOverrides && Object.keys(opts.stageOverrides).length) {
      body.stage_overrides = opts.stageOverrides
    }
    const r = await apiFetch('/comms/features/decompose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    return await r.json() as { ok: boolean; reason?: string; run_id?: string }
  } catch {
    return null
  }
}

// Decompose a whole PROJECT into sibling features (POST /comms/project/decompose).
// rigor: light → planning/project-decompose skill · full → planner · consultation → FSM flow.
export async function apiDecomposeProject(
  project: string,
  rigor: 'light' | 'full' | 'consultation',
  opts: { projectRoot?: string; adapter?: string; stageOverrides?: Record<string, string> } = {},
): Promise<{ ok: boolean; reason?: string; run_id?: string } | null> {
  try {
    const body: Record<string, unknown> = { project, rigor }
    if (opts.projectRoot) body.project_root = opts.projectRoot
    if (opts.adapter) body.adapter = opts.adapter
    // Transient per-stage trims from the flow gate (FlowGatePreview) — rigor='consultation' only.
    if (opts.stageOverrides && Object.keys(opts.stageOverrides).length) {
      body.stage_overrides = opts.stageOverrides
    }
    const r = await apiFetch('/comms/project/decompose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    return await r.json() as { ok: boolean; reason?: string; run_id?: string }
  } catch {
    return null
  }
}

// Stop a single-task run (kills its board run, reverts the task to pending).
export async function apiStopTask(taskId: string): Promise<boolean> {
  try {
    const r = await apiFetch('/comms/tasks/stop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message_id: taskId }),
    })
    return r.ok
  } catch {
    return false
  }
}
