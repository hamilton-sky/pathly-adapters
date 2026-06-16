import type { Message, Feature, FeatureStatus, BoardScope, MessageType, Stage, QuestionOption, AgentId } from '../components/CommandCenter/types'
import { readFile, listDir } from '../services/pathlyApi'

import { apiFetch } from '../lib/config'

// ── Relative-time helper ─────────────────────────────────────────────

export function relativeTime(isoTs: string): string {
  const ms = Date.now() - new Date(isoTs).getTime()
  if (ms < 60_000) return 'now'
  const mins = Math.floor(ms / 60_000)
  if (mins < 60) return `${mins}m`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h`
  const days = Math.floor(hrs / 24)
  if (days < 7) return `${days}d`
  const wks = Math.floor(days / 7)
  return `${wks}w`
}

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
  deleted_at: string | null
  artifact_path: string | null
  artifact_type: string | null
  artifact_url: string | null
  superseded_by?: string | null
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
    time: relativeTime(row.ts),
    ts: row.ts,
    pinned: row.type === 'decision',
    ack: ackedBy.length > 0,
    readByAgent,
  }

  if (row.status) m.status = row.status as Message['status']
  if (options) m.options = options

  if (row.type === 'artifact' && row.artifact_path) {
    m.artifact = basename(row.artifact_path)
    m.artifactPath = row.artifact_path
    if (row.artifact_type) m.atype = row.artifact_type as Message['atype']
  }

  if (row.superseded_by) m.supersededBy = row.superseded_by

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
}

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

// ── Feature list + per-feature enrichment from STATE.json ─────────────

interface FeatureState {
  current?: string
  convs_done?: number
  convs_total?: number
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

/** Resolve the storage path for a feature: new-style pathly/<id>/ wins if it exists,
 *  otherwise falls back to pathly/plans/<id>/. Mirrors _resolve_storage_path in fsm_ops.py. */
async function resolveFeaturePath(projectPath: string, featureId: string): Promise<string> {
  const newStyle = `${projectPath}/pathly/${featureId}`
  // listDir on the dir itself returns [] when the dir doesn't exist, but we need to know
  // if the dir exists. Writing a .keep file ensures the new-style dir exists, so we check
  // for that sentinel. If absent, fall through to the legacy path.
  const sentinel = await readFile(`${newStyle}/.keep`)
  if (sentinel !== null) return newStyle
  // Also accept new-style dirs that have any files already (e.g. STATE.json written by FSM)
  const anyFile = await readFile(`${newStyle}/STATE.json`)
  if (anyFile !== null) return newStyle
  return `${projectPath}/pathly/plans/${featureId}`
}

/** Read a feature's STATE.json (filesystem) — current stage + conversation count. */
export async function fetchFeatureState(projectPath: string, featureId: string): Promise<FeatureState | null> {
  try {
    const base = await resolveFeaturePath(projectPath, featureId)
    const raw = await readFile(`${base}/STATE.json`)
    if (!raw) return null
    return JSON.parse(raw) as FeatureState
  } catch {
    return null
  }
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

interface AgentDoneEvent {
  type?: string
  agent?: string
  summary?: string
}

function summarize(agent: string | undefined, summary: string): string {
  const clean = summary.replace(/\s+/g, ' ').trim()
  const text = clean.length > 160 ? `${clean.slice(0, 159)}…` : clean
  return agent ? `${agent}: ${text}` : text
}

/** Latest AGENT_DONE summary from a feature's EVENTS.jsonl — the card's "last activity" line. */
export async function fetchLastSummary(projectPath: string, featureId: string): Promise<string> {
  try {
    const base = await resolveFeaturePath(projectPath, featureId)
    const raw = await readFile(`${base}/EVENTS.jsonl`)
    if (!raw) return ''
    const lines = raw.split('\n')
    for (let i = lines.length - 1; i >= 0; i--) {
      const line = lines[i].trim()
      if (!line) continue
      try {
        const ev = JSON.parse(line) as AgentDoneEvent
        if (ev.type === 'AGENT_DONE' && ev.summary && ev.summary.trim()) {
          return summarize(ev.agent, ev.summary)
        }
      } catch {
        // skip a malformed line and keep scanning backwards
      }
    }
    return ''
  } catch {
    return ''
  }
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
    conv: state?.convs_done ?? 0,
    status,
    agent: STAGE_AGENT[stage],
    last,
    scope: { feature: true, project: true, global: true },
  }
}
