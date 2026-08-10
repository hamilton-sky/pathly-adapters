import type { Message, Feature, FeatureStatus, BoardScope, MessageType, Stage, QuestionOption, AgentId } from '../components/CommandCenter/types'
import { listDir, listDirs } from '../services/pathlyApi'

import { apiFetch } from '../lib/config'

// ── Backend row shape ────────────────────────────────────────────────

export interface CommsRow {
  id: string
  board: string
  scope: string
  from_agent: string
  to_agent: string | null
  type: string
  text: string
  options: string | null
  reply_to: string | null
  stage: string | null
  conv: number | null
  ts: string
  read_by: string | null
  acknowledged_by: string | null
  status: string | null
  /** Question rows only: the option id the human chose (persisted by /comms/answer). */
  answer_option?: string | null
  deleted_at: string | null
  artifact_path: string | null
  artifact_type: string | null
  artifact_url: string | null
  superseded_by?: string | null
  goal_id?: string | null
  executor?: string | null
  task_status?: string | null
  depends_on?: string | null
  /** Semantic-search only: the child chunk that matched (search_by_embedding). */
  _matched_chunk?: string | null
  /** Hybrid search: which arm matched this row ('keyword' | 'semantic'). */
  _match_source?: string | null
  /** Semantic hit: cosine distance (lower = closer). */
  _distance?: number | null
}

interface BackendOption {
  id: string
  label: string
  description?: string
}

// Map the server's from_agent to the display identity. 'human' becomes 'you';
// every other role is preserved as-is (explorer, evaluator, system, …) so the
// card shows who actually posted instead of collapsing unknowns to 'builder'.
function toAgentId(raw: string): string {
  return raw === 'human' ? 'you' : raw
}

function parseJsonArray(raw: string | null): string[] {
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function parseOptions(raw: string | null): QuestionOption[] | undefined {
  if (!raw) return undefined
  try {
    const parsed = JSON.parse(raw) as BackendOption[]
    if (!Array.isArray(parsed)) return undefined
    return parsed.map((o) => ({ id: o.id, label: o.label, desc: o.description }))
  } catch {
    return undefined
  }
}

function basename(path: string | null): string | undefined {
  if (!path) return undefined
  return path.split(/[/\\]/).pop()
}

// ── Row → Message adapter ────────────────────────────────────────────

export function rowToMessage(row: CommsRow): Message {
  const readBy = parseJsonArray(row.read_by)
  const ackedBy = parseJsonArray(row.acknowledged_by)
  const readByAgent = readBy.some((r) => r !== 'you' && r !== 'human')
  const options = parseOptions(row.options)

  const m: Message = {
    id: row.id,
    type: row.type as Message['type'],
    from: toAgentId(row.from_agent),
    text: row.text,
    stage: (row.stage as Stage) ?? null,
    ts: row.ts,
    pinned: row.type === 'decision',
    ack: ackedBy.length > 0,
    readByAgent,
  }

  if (row.status) m.status = row.status as Message['status']
  if (options) m.options = options
  // The chosen option id — restores the selected-option highlight on a board reload
  // (the CardBody marks an option chosen via `m.answer === option.id`).
  if (row.answer_option) m.answer = row.answer_option

  if (row.type === 'artifact' && row.artifact_path) {
    m.artifact = basename(row.artifact_path)
    m.artifactPath = row.artifact_path
    if (row.artifact_type) m.atype = row.artifact_type as Message['atype']
  }

  if (row.superseded_by) m.supersededBy = row.superseded_by
  if (row.goal_id) m.goal_id = row.goal_id
  if (row.executor) m.executor = row.executor as Message['executor']
  if (row.task_status) m.taskStatus = row.task_status as Message['taskStatus']
  const deps = parseJsonArray(row.depends_on ?? null)
  if (deps.length > 0) m.dependsOn = deps
  if (row._matched_chunk) m.matchedChunk = row._matched_chunk
  if (row._match_source === 'keyword' || row._match_source === 'semantic') {
    m.matchSource = row._match_source
  }
  if (typeof row._distance === 'number') m.distance = row._distance

  return m
}

// ── comms_artifacts side-table ───────────────────────────────────────

/** A stored artifact row (one per file produced on a board, many-per-task). */
export interface ArtifactRow {
  id: string
  message_id: string
  path: string
  type: string | null
  title: string | null
  summary: string | null
  token_count: number | null
  created_at: string
  created_by: string | null
  last_edit_at: string | null
  last_edit_by: string | null
  version: number | null
  supersedes: string | null
  /** JSON-encoded AiSelection {type,id} — the saved per-artifact summary target. */
  summary_selection?: string | null
  /** Per-artifact summary DEPTH style; null → the default ('topic-map'). */
  summary_style?: SummaryStyle | null
  /** Per-artifact free-text "special request" appended to the summary prompt; null → none. */
  summary_note?: string | null
}

/** Summary DEPTH style — selects which development/summarize* skill the client composes. */
export type SummaryStyle = 'gist' | 'topic-map' | 'detailed'
export const SUMMARY_STYLE_DEFAULT: SummaryStyle = 'topic-map'

/** Fetch the artifacts linked to a message. Returns [] on any failure. */
export async function fetchArtifacts(messageId: string): Promise<ArtifactRow[]> {
  try {
    const r = await apiFetch(`/comms/artifacts?message_id=${encodeURIComponent(messageId)}`)
    const data = (await r.json()) as { ok?: boolean; artifacts?: ArtifactRow[] }
    return Array.isArray(data.artifacts) ? data.artifacts : []
  } catch {
    return []
  }
}

// ── boardKey convention ──────────────────────────────────────────────

export function scopeToParams(scope: BoardScope, key: string): { board: string; scope: string } {
  if (scope === 'feature') return { board: 'feature', scope: key }
  if (scope === 'project') return { board: 'project', scope: key.replace(/\\/g, '/').replace(/\/$/, '') }
  return { board: 'global', scope: 'global' }
}

// ── Fetch helpers ─────────────────────────────────────────────────────

export async function fetchBoard(
  feature: string,
  board: string,
  scope: string,
): Promise<Message[]> {
  try {
    const params = new URLSearchParams({ feature, board, scope })
    const r = await apiFetch(`/comms?${params}`)
    if (!r.ok) return []
    const rows = await r.json() as CommsRow[]
    return rows.map(rowToMessage)
  } catch {
    return []
  }
}

export async function apiPost(
  feature: string,
  board: string,
  scope: string,
  type: MessageType,
  text: string,
  stage?: Stage | null,
): Promise<string | null> {
  try {
    const r = await apiFetch(`/comms/post`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ feature, from: 'human', type, text, board, scope, stage: stage ?? null }),
    })
    if (!r.ok) return null
    const json = await r.json() as { message_id: string }
    return json.message_id
  } catch {
    return null
  }
}

/**
 * Post a type='note' message. The text should start with task title(s) so hybrid
 * retrieval surfaces the note when agents query context about those tasks.
 * dependsOn = task message IDs this note is attached to.
 */
export async function apiPostNote(
  feature: string,
  board: string,
  scope: string,
  text: string,
  goalId?: string,
  dependsOn?: string[],
): Promise<string | null> {
  try {
    const r = await apiFetch('/comms/post', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        feature, from: 'human', type: 'note', text, board, scope,
        ...(goalId ? { goal_id: goalId } : {}),
        ...(dependsOn?.length ? { depends_on: dependsOn } : {}),
      }),
    })
    if (!r.ok) return null
    const json = await r.json() as { message_id?: string }
    return json.message_id ?? null
  } catch {
    return null
  }
}

/**
 * Post a type='artifact' message that points at a file path, so it renders as an
 * artifact card AND the backend creates its comms_artifacts metadata row. Returns
 * the new message id, or null on failure.
 */
export async function apiPostArtifact(
  feature: string,
  board: string,
  scope: string,
  text: string,
  artifactPath: string,
  artifactType?: string,
  summaryBackend?: string,
  embedSummary?: boolean,
): Promise<string | null> {
  try {
    const r = await apiFetch(`/comms/post`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        feature, from: 'human', type: 'artifact', text, board, scope,
        artifact_path: artifactPath,
        ...(artifactType ? { artifact_type: artifactType } : {}),
        ...(summaryBackend ? { summary_backend: summaryBackend } : {}),
        ...(embedSummary ? { embed_summary: true } : {}),
      }),
    })
    if (!r.ok) return null
    const json = await r.json() as { message_id?: string }
    return json.message_id ?? null
  } catch {
    return null
  }
}

// ── unified-ai-routing (Conv 3): client-side summary + per-artifact target ──

/** AiSelection mirror — kept structural so commsApi doesn't import the service layer. */
export interface AiSelectionDto {
  type: 'model' | 'engine'
  id: string
}

/**
 * Write a CLIENT-computed summary back to comms_artifacts (the renderer runs
 * aiRouter, then posts the text here — the server runs no inference). Pass
 * `selection` to also persist the target that produced it. Returns true on 2xx.
 */
export async function apiSetArtifactSummary(
  artifactId: string,
  summary: string,
  selection?: AiSelectionDto,
): Promise<boolean> {
  try {
    const r = await apiFetch(`/comms/artifacts/${encodeURIComponent(artifactId)}/summary`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ summary, ...(selection ? { selection } : {}) }),
    })
    return r.ok
  } catch {
    return false
  }
}

/** Persist a per-artifact AI target (so Re-summarize reuses it). Returns true on 2xx. */
export async function apiSetArtifactSelection(
  artifactId: string,
  selection: AiSelectionDto,
): Promise<boolean> {
  try {
    const r = await apiFetch(`/comms/artifacts/${encodeURIComponent(artifactId)}/selection`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ selection }),
    })
    return r.ok
  } catch {
    return false
  }
}

/** Persist a per-artifact summary DEPTH style (so Re-summarize reuses it). Returns true on 2xx. */
export async function apiSetArtifactStyle(
  artifactId: string,
  style: SummaryStyle,
): Promise<boolean> {
  try {
    const r = await apiFetch(`/comms/artifacts/${encodeURIComponent(artifactId)}/style`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ style }),
    })
    return r.ok
  } catch {
    return false
  }
}

/** Persist a per-artifact free-text "special request" (appended to the summary prompt). */
export async function apiSetArtifactNote(
  artifactId: string,
  note: string,
): Promise<boolean> {
  try {
    const r = await apiFetch(`/comms/artifacts/${encodeURIComponent(artifactId)}/note`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note }),
    })
    return r.ok
  } catch {
    return false
  }
}

/** Fetch the app-default summary AiSelection, or null when unset / on error. */
export async function apiGetDefaultSelection(): Promise<AiSelectionDto | null> {
  try {
    const r = await apiFetch('/comms/default-selection')
    if (!r.ok) return null
    const json = (await r.json()) as { selection?: AiSelectionDto | null }
    return json.selection ?? null
  } catch {
    return null
  }
}

/** Persist the app-default summary AiSelection. Returns true on 2xx. */
export async function apiSetDefaultSelection(selection: AiSelectionDto): Promise<boolean> {
  try {
    const r = await apiFetch('/comms/default-selection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ selection }),
    })
    return r.ok
  } catch {
    return false
  }
}

/** Fetch the app-default summary depth style, or null when unset / on error. */
export async function apiGetDefaultStyle(): Promise<SummaryStyle | null> {
  try {
    const r = await apiFetch('/comms/default-style')
    if (!r.ok) return null
    const json = (await r.json()) as { style?: SummaryStyle | null }
    return json.style ?? null
  } catch {
    return null
  }
}

/** Persist the app-default summary depth style. Returns true on 2xx. */
export async function apiSetDefaultStyle(style: SummaryStyle): Promise<boolean> {
  try {
    const r = await apiFetch('/comms/default-style', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ style }),
    })
    return r.ok
  } catch {
    return false
  }
}

// ── spawn-policy: per-agent model policy + logging config ─────────────
// One DB-backed control plane read by BOTH the renderer gate and the Python resolver, so a
// spawn's model + narration are chosen the same way everywhere. Mirrors the default-progress
// pair above. The always-on cost/monitor spine is deliberately NOT exposed (SPEC §0 invariant).

/** One {company, model} selection. `model` '' = that company's own engine default. */
export interface ModelSel {
  adapter: string
  model: string
}

/** The full per-agent model policy for the Settings UI. */
export interface ModelPolicy {
  /** Global default applied to every spawn without a per-role override; null = engine default. */
  default: ModelSel | null
  /** Per-role/per-place overrides, keyed by the agent/telemetry identity (architect, split, …). */
  roles: Record<string, ModelSel>
}

/** Fetch the per-agent model policy, or null on error. */
export async function apiGetModelPolicy(): Promise<ModelPolicy | null> {
  try {
    const r = await apiFetch('/comms/model-policy')
    if (!r.ok) return null
    const j = (await r.json()) as Partial<ModelPolicy>
    return { default: j.default ?? null, roles: j.roles ?? {} }
  } catch {
    return null
  }
}

/** Set the global default (role null) or a per-role override. `model` '' = engine default. */
export async function apiSetModelPolicy(
  role: string | null,
  adapter: string,
  model: string,
): Promise<boolean> {
  try {
    const r = await apiFetch('/comms/model-policy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role, adapter, model }),
    })
    return r.ok
  } catch {
    return false
  }
}

/** Clear the global default (role null) or a per-role override (falls back to the default). */
export async function apiClearModelPolicy(role: string | null): Promise<boolean> {
  try {
    const r = await apiFetch('/comms/model-policy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role, clear: true }),
    })
    return r.ok
  } catch {
    return false
  }
}

/** One agent role from the registry (seeded from core/agents/), for the model-policy UI. */
export interface AgentDef {
  role: string
  name: string
  model: string
  description: string
}

/** Fetch the known agent roles from the registry, or [] on error (UI falls back to built-ins). */
export async function apiGetAgents(projectRoot?: string): Promise<AgentDef[]> {
  try {
    const q = projectRoot ? `?project_root=${encodeURIComponent(projectRoot)}` : ''
    const r = await apiFetch(`/db/agents${q}`)
    if (!r.ok) return []
    const j = (await r.json()) as { agents?: AgentDef[] }
    return Array.isArray(j.agents) ? j.agents : []
  } catch {
    return []
  }
}

/** A priced model row (one model + its $/MTok rates), for the model dropdowns. */
export interface PricingModel {
  model: string
  input: number
  output: number
}
/** Priced models keyed by provider slug (claude/codex/antigravity/…). */
export type PricingByProvider = Record<string, PricingModel[]>

/** Fetch the provider pricing table (models per provider + $/MTok), or {} on error. */
export async function apiGetPricing(): Promise<PricingByProvider> {
  try {
    const r = await apiFetch('/telemetry/pricing')
    if (!r.ok) return {}
    const j = (await r.json()) as {
      providers?: Record<string, Record<string, { input: number; output: number }>>
    }
    const out: PricingByProvider = {}
    for (const [provider, models] of Object.entries(j.providers ?? {})) {
      out[provider] = Object.entries(models).map(([model, rate]) => ({
        model,
        input: rate.input,
        output: rate.output,
      }))
    }
    return out
  } catch {
    return {}
  }
}

export async function apiAnswer(
  questionId: string,
  answer: string,
  optionId?: string,
): Promise<boolean> {
  try {
    const r = await apiFetch(`/comms/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question_id: questionId, answer, option_id: optionId }),
    })
    return r.ok
  } catch {
    return false
  }
}

export async function apiAcknowledge(messageId: string, agent: string): Promise<boolean> {
  try {
    const r = await apiFetch(`/comms/acknowledge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message_id: messageId, agent }),
    })
    return r.ok
  } catch {
    return false
  }
}

export async function apiToggleScope(
  feature: string,
  projectRoot: string,
  scope: { feature: boolean; project: boolean; global: boolean },
): Promise<boolean> {
  try {
    const r = await apiFetch(`/comms/scope`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ feature, project_root: projectRoot, scope }),
    })
    return r.ok
  } catch {
    return false
  }
}

export async function apiDelete(messageId: string, force = false): Promise<boolean> {
  try {
    const r = await apiFetch(`/comms/delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message_id: messageId, force }),
    })
    return r.ok
  } catch {
    return false
  }
}

/** Edit a message's text in place (board UI — rename a goal). Returns true on 2xx. */
export async function apiEditMessage(messageId: string, text: string): Promise<boolean> {
  try {
    const r = await apiFetch(`/comms/edit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message_id: messageId, text }),
    })
    return r.ok
  } catch {
    return false
  }
}

// ── GAP 2: resolve → FSM decision gate ───────────────────────────────
export async function apiRunnerDecision(topic: string, decision: string): Promise<boolean> {
  try {
    const r = await apiFetch(`/runner/decision`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic, decision }),
    })
    return r.ok
  } catch {
    return false
  }
}

export async function apiRunnerAwaitingDecision(topic: string): Promise<string[] | null> {
  try {
    const r = await apiFetch(`/runner/status?topic=${encodeURIComponent(topic)}`)
    if (!r.ok) return null
    const s = await r.json() as { status?: string; pending_menu?: { options?: Record<string, string> } }
    if (s.status !== 'awaiting_decision' || !s.pending_menu?.options) return null
    return Object.keys(s.pending_menu.options)
  } catch {
    return null
  }
}

/**
 * Current FSM runner status for a topic ('running' | 'paused' | 'awaiting_decision' |
 * 'done' | 'aborted' | 'error' | …), 'gone' when no run exists (404), or null on a network
 * error. Used to track a board-launched FSM-flow run (project/feature consultation) — which,
 * unlike a single-agent board run, holds NO board-lock, so apiBoardRunStatus can't see it.
 */
export async function apiRunnerStatus(topic: string): Promise<string | null> {
  try {
    const r = await apiFetch(`/runner/status?topic=${encodeURIComponent(topic)}`)
    if (r.status === 404) return 'gone'
    if (!r.ok) return null
    const s = await r.json() as { status?: string }
    return s.status ?? 'gone'
  } catch {
    return null
  }
}

// ── GAP 4(a): hybrid search ──────────────────────────────────────────
export async function apiSearch(
  query: string,
  feature: string,
  board: string,
  scope: string,
): Promise<Message[]> {
  try {
    const r = await apiFetch(`/comms/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, feature, board, scope, mode: 'hybrid' }),
    })
    if (!r.ok) return []
    const rows = await r.json() as CommsRow[]
    return rows.map(rowToMessage)
  } catch {
    return []
  }
}

// ── GAP 4(b): supersede ──────────────────────────────────────────────
export async function apiSupersede(oldId: string, newId: string): Promise<boolean> {
  try {
    const r = await apiFetch(`/comms/supersede`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ old_id: oldId, new_id: newId }),
    })
    return r.ok
  } catch {
    return false
  }
}

// ── GAP 4(c): attach ─────────────────────────────────────────────────
export async function apiAttach(
  messageId: string,
  artifactPath: string,
  artifactType?: Message['atype'],
): Promise<boolean> {
  try {
    const r = await apiFetch(`/comms/attach`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message_id: messageId,
        artifact_path: artifactPath,
        artifact_type: artifactType ?? null,
      }),
    })
    return r.ok
  } catch {
    return false
  }
}

// ── C2: single-agent run ─────────────────────────────────────────────

export interface RunBoardResult {
  ok: true
  run_id: string
  mode: string
  result: unknown
}

export interface RunBoardBusy {
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

// ── Goal DAG run ─────────────────────────────────────────────────────

export interface RunGoalResult {
  ok: true
  run_id: string
  executor: string
}

export interface RunGoalBusy {
  ok: false
  error: 'board_busy'
  reason?: string
}

export interface RunGoalTeamUnavailable {
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

// ── Feature list + per-feature enrichment (DB-first /db/features rows) ─

interface FeatureState {
  current?: string
}

// FSM state name → kit Stage (the card's 6-stage colour vocabulary).
const STAGE_MAP: Record<string, Stage> = {
  STORM: 'PLANNING', STORMING: 'PLANNING',
  PLAN: 'PLANNING', PLANNING: 'PLANNING',
  DESIGN: 'PLANNING', DESIGNING: 'PLANNING',
  BUILD: 'BUILDING', BUILDING: 'BUILDING',
  REVIEW: 'REVIEWING', REVIEWING: 'REVIEWING',
  TEST: 'TESTING', TESTING: 'TESTING',
  RETRO: 'RETRO', RETROSPECTIVE: 'RETRO',
  DONE: 'DONE',
}

function toStage(current: string | undefined): Stage {
  if (!current) return 'PLANNING'
  return STAGE_MAP[current.toUpperCase()] ?? 'PLANNING'
}

const STAGE_AGENT: Record<Stage, AgentId> = {
  PLANNING: 'architect',
  BUILDING: 'builder',
  REVIEWING: 'reviewer',
  TESTING: 'tester',
  RETRO: 'retro',
  DONE: 'retro',
}

// An open feedback file means the stage is blocked on a human/agent response.
const BLOCKER_FILES = new Set([
  'REVIEW_FAILURES.md', 'TEST_FAILURES.md',
  'HUMAN_QUESTIONS.md', 'IMPL_QUESTIONS.md', 'DESIGN_QUESTIONS.md',
])

// ── DB-first feature map (state-one-authority) ────────────────────────
// One /db/features fetch per burst — replaces the per-feature STATE.json /
// EVENTS.jsonl mirror reads. The short TTL dedupes loadFeatures' Promise.all
// fan-out into a single HTTP call; pass { fresh: true } to bypass it.
let dbFeatureMapCache: { root: string; at: number; map: Promise<Map<string, DbFeature>> } | null = null
const DB_FEATURE_MAP_TTL_MS = 2000

export function fetchDbFeatureMap(
  projectRoot: string,
  opts?: { fresh?: boolean },
): Promise<Map<string, DbFeature>> {
  const now = Date.now()
  if (
    !opts?.fresh &&
    dbFeatureMapCache &&
    dbFeatureMapCache.root === projectRoot &&
    now - dbFeatureMapCache.at < DB_FEATURE_MAP_TTL_MS
  ) {
    return dbFeatureMapCache.map
  }
  const map = window.pathly.db
    .features(projectRoot)
    .then((rows) => new Map((rows ?? []).map((r) => [r.feature, r])))
    .catch(() => new Map<string, DbFeature>())
  dbFeatureMapCache = { root: projectRoot, at: now, map }
  return map
}

/** Resolve the storage path for a feature. Mirrors _resolve_storage_path in fsm_ops.py:
 *  the feature-centric home pathly/features/<id>/ wins, then new-style pathly/<id>/.
 *  Existence is probed via container listings — never a STATE.json mirror read
 *  (state-one-authority: runtime state lives in the DB). */
export async function resolveFeaturePath(projectPath: string, featureId: string): Promise<string> {
  const featureDir = `${projectPath}/pathly/features/${featureId}`
  const featureNames = await listDirs(`${projectPath}/pathly/features`).catch(() => [] as string[])
  if (featureNames.includes(featureId)) return featureDir
  const topLevelNames = await listDirs(`${projectPath}/pathly`).catch(() => [] as string[])
  if (topLevelNames.includes(featureId)) return `${projectPath}/pathly/${featureId}`
  // Default to the feature-centric home (legacy pathly/plans/<id>/ fallback removed post-migration).
  return featureDir
}

/** A feature's current stage — from its DB-first /db/features row (state-one-authority). */
export async function fetchFeatureState(projectPath: string, featureId: string): Promise<FeatureState | null> {
  const row = (await fetchDbFeatureMap(projectPath)).get(featureId)
  if (!row) return null
  return { current: row.state !== 'UNKNOWN' ? row.state : undefined }
}

/** A feature is blocked when its feedback/ folder holds an open failure/question file. */
export async function featureBlocked(projectPath: string, featureId: string): Promise<boolean> {
  try {
    const base = await resolveFeaturePath(projectPath, featureId)
    const files = await listDir(`${base}/feedback`).catch(() => [] as string[])
    return files.some((f) => BLOCKER_FILES.has(f))
  } catch {
    return false
  }
}

function summarize(agent: string | undefined, summary: string): string {
  const clean = summary.replace(/\s+/g, ' ').trim()
  const text = clean.length > 160 ? `${clean.slice(0, 159)}…` : clean
  return agent ? `${agent}: ${text}` : text
}

/** Latest AGENT_DONE summary — from the DB row's last_summary (state-one-authority);
 *  the card's "last activity" line. */
export async function fetchLastSummary(projectPath: string, featureId: string): Promise<string> {
  const row = (await fetchDbFeatureMap(projectPath)).get(featureId)
  if (!row?.last_summary?.trim()) return ''
  return summarize(undefined, row.last_summary)
}

export function buildFeature(
  id: string,
  state?: FeatureState | null,
  blocked = false,
  last = '',
): Feature {
  const stage = toStage(state?.current)
  const status: FeatureStatus = stage === 'DONE' ? 'done' : blocked ? 'blocked' : 'idle'
  return {
    id,
    stage,
    status,
    agent: STAGE_AGENT[stage],
    last,
    scope: { feature: true, project: true, global: true },
  }
}
