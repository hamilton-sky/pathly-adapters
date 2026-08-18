// Running work ON a board: the single-agent run (C2) and the board-scoped flow run that the
// footer launcher starts via /runner/start.

import { apiFetch } from '../../lib/config'


interface RunBoardResult {
  ok: true
  run_id: string
  mode: string
  result: unknown
}

interface RunBoardBusy {
  ok: false
  error: 'board_busy'
}

export type RunBoardResponse = RunBoardResult | RunBoardBusy

export interface RunBoardOpts {
  projectRoot?: string
  agent?: string
  skill?: string
  /** Preset system-prompt text (the "System prompt" selector). */
  systemPrompt?: string
  interactive?: boolean
  /** Which CLI to spawn: 'claude' | 'codex' | 'antigravity'. */
  adapter?: string
  /** The agent's task — sent directly so it doesn't depend on board-post timing. */
  instructions?: string
  /** Headless board-progress verbosity: 'quiet' | 'normal' | 'verbose'. */
  progress?: string
  /** Layer-3 ability library row ids to compose after the skill's fragments. */
  abilityIds?: string[]
  /** Gate "use once" prompt override (Sections trim) — sent verbatim instead of composing. */
  promptOverride?: string
}

export async function apiRunBoard(
  board: string,
  scope: string,
  mode: string,
  opts: RunBoardOpts = {},
): Promise<RunBoardResponse | null> {
  try {
    const body: Record<string, unknown> = { board, scope, mode }
    if (opts.projectRoot !== undefined) body.project_root = opts.projectRoot
    if (opts.agent) body.agent = opts.agent
    if (opts.skill) body.skill = opts.skill
    if (opts.systemPrompt) body.system_prompt = opts.systemPrompt
    if (opts.interactive) body.interactive = true
    if (opts.adapter) body.adapter = opts.adapter
    if (opts.instructions) body.instructions = opts.instructions
    if (opts.progress) body.progress = opts.progress
    if (opts.abilityIds?.length) body.ability_ids = opts.abilityIds
    if (opts.promptOverride) body.prompt_override = opts.promptOverride
    const r = await apiFetch('/comms/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    return await r.json() as RunBoardResponse
  } catch {
    return null
  }
}

/**
 * Whether a board currently has an active runner (the board-lock is held), plus the
 * holding run id. Used by the store's completion watcher to clear a board-run pill
 * without depending on the comms SSE. Returns null when unreachable (e.g. an older
 * server without this route) so the caller keeps watching rather than false-completing.
 */
export async function apiBoardRunStatus(
  board: string,
  scope: string,
): Promise<{ running: boolean; holder: string | null } | null> {
  try {
    const r = await apiFetch(`/comms/run/status?board=${encodeURIComponent(board)}&scope=${encodeURIComponent(scope)}`)
    if (!r.ok) return null
    const j = (await r.json()) as { running?: boolean; holder?: string | null }
    return { running: Boolean(j.running), holder: j.holder ?? null }
  } catch {
    return null
  }
}

/** Stop the agent currently running on a board. */
export async function apiStopBoard(board: string, scope: string): Promise<boolean> {
  try {
    const r = await apiFetch('/comms/run/stop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ board, scope }),
    })
    return r.ok
  } catch {
    return false
  }
}

/**
 * Stop a run by run_id (unified-control-plane control) — POST /runs/<run_id>/stop resolves it to
 * the right stop path server-side (FSM abort for a flow/team/consultation, board-lock stop for a
 * board single/evaluator or goal single/loop). Idempotent; returns true on 2xx.
 */
export async function apiStopRun(runId: string): Promise<boolean> {
  try {
    const r = await apiFetch(`/runs/${encodeURIComponent(runId)}/stop`, { method: 'POST' })
    return r.ok
  } catch {
    return false
  }
}

/**
 * Run_id-addressed control action (unified-control-plane T2) — POST /runs/<run_id>/<action>.
 * Only meaningful against an ACTIVE FSM-registry run (pause/resume/advance/reroute) or a
 * FINISHED one (retry); a board-lock run (single/loop/evaluator) only supports 'abort', which
 * `apiStopRun` already covers. The server responds 200 even for a semantic no-op (e.g.
 * {ok:false, reason:'unsupported_for_kind'|'not_active'}) — this helper reports transport
 * success only, so callers gate which buttons appear (RunControls) rather than branch on the
 * response body.
 */
export async function apiRunAction(
  runId: string,
  action: 'pause' | 'resume' | 'advance' | 'reroute' | 'retry' | 'abort',
  body?: Record<string, unknown>,
): Promise<boolean> {
  try {
    const r = await apiFetch(`/runs/${encodeURIComponent(runId)}/${action}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body ?? {}),
    })
    return r.ok
  } catch {
    return false
  }
}

/**
 * Thin RunSpec for the unified launcher (unified-control-plane T5/T6) — mirrors the server's
 * ``POST /runs`` body. ``board``/``scope`` apply to kind 'single'|'evaluator' (and 'flow',
 * which only reads 'scope'); 'goal' only reads ``goalId``. Sending the unused fields anyway is
 * harmless — the server ignores whatever a given kind doesn't need.
 */
export interface RunSpec {
  kind: 'flow' | 'single' | 'evaluator' | 'goal'
  board?: 'feature' | 'project' | 'global'
  scope?: string
  flow?: string
  goalId?: string
  adapter?: string
  model?: string
  projectRoot?: string
}

/**
 * Launch any run kind from one place — POST /runs (unified-control-plane T5/T6 launcher). The
 * server routes the RunSpec to the matching existing facade (start_run / start_board_run /
 * start_goal_run) and replies { ok, run_id, kind } on success, or an error body ({ error } on a
 * 400, { ok:false, error } on a 409 busy) — both still parsed and returned, not treated as a
 * transport failure. Returns null only when the request itself couldn't be sent.
 */
export async function apiCreateRun(
  spec: RunSpec,
): Promise<{ ok: boolean; run_id?: string; kind?: string; error?: string } | null> {
  try {
    const r = await apiFetch('/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        kind: spec.kind,
        board: spec.board,
        scope: spec.scope,
        ...(spec.flow ? { flow: spec.flow } : {}),
        ...(spec.goalId ? { goal_id: spec.goalId } : {}),
        ...(spec.adapter ? { adapter: spec.adapter } : {}),
        ...(spec.model ? { model: spec.model } : {}),
        project_root: spec.projectRoot ?? '',
      }),
    })
    const j = (await r.json()) as { ok?: boolean; run_id?: string; kind?: string; error?: string }
    return { ok: j.ok ?? r.ok, run_id: j.run_id, kind: j.kind, error: j.error }
  } catch {
    return null
  }
}

/** Stop the executor running for a goal (single, loop, or team). */
export async function apiStopGoal(goalId: string): Promise<boolean> {
  try {
    const r = await apiFetch('/comms/goals/stop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ goal_id: goalId }),
    })
    return r.ok
  } catch {
    return false
  }
}

/**
 * Hydrate a project's on-disk BOARD.json mirrors back into the DB (board disk-mirror
 * P2 — the fresh-clone story). Best-effort and DB-authoritative: it no-ops for any
 * board that already has rows, so it's safe to call on every project open. Returns the
 * hydrated/skipped scopes, or null on failure.
 */
export async function apiHydrateBoards(
  projectRoot: string,
): Promise<{ hydrated: string[]; skipped: string[] } | null> {
  try {
    const r = await apiFetch('/comms/hydrate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_root: projectRoot }),
    })
    if (!r.ok) return null
    return await r.json() as { hydrated: string[]; skipped: string[] }
  } catch {
    return null
  }
}

// ── Board-scoped flow run (footer launcher → /runner/start) ──────────

export interface StartFlowOpts {
  projectRoot?: string
  interactive?: boolean
  maxIterations?: number
  maxCostUsd?: number
  model?: string
  /** Transient, per-run, per-stage prompt overrides from the flow gate (FlowGatePreview),
   *  keyed by FSM state. Sent as `stage_overrides` only when non-empty. */
  stageOverrides?: Record<string, string>
}

/**
 * Launch a board-scoped pipeline run — a flow that does NOT depend on a goal/DAG
 * (debug, quick-fix, explore, test, team). `topic` is the board's feature/scope.
 * Body mirrors the FlowControlBar Start button so stages spawn as terminals the
 * same way. Returns { ok, busy } — busy=true when a run for that topic is active.
 */
export async function apiStartFlow(
  topic: string,
  flow: string,
  opts: StartFlowOpts = {},
): Promise<{ ok: boolean; busy?: boolean }> {
  try {
    const r = await apiFetch('/runner/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        topic,
        flow,
        project_root: opts.projectRoot ?? '',
        max_iterations: opts.maxIterations ?? 50,
        max_cost_usd: opts.maxCostUsd ?? 10,
        interactive: opts.interactive ?? true,
        ...(opts.model ? { model: opts.model } : {}),
        ...(opts.stageOverrides && Object.keys(opts.stageOverrides).length
          ? { stage_overrides: opts.stageOverrides }
          : {}),
      }),
    })
    if (r.status === 409) return { ok: false, busy: true }
    return { ok: r.ok }
  } catch {
    return { ok: false }
  }
}
