import type { Message, Feature, FeatureStatus, BoardScope, MessageType, Stage, QuestionOption, AgentId } from '../components/CommandCenter/types'
import { readFile, listDir } from '../services/pathlyApi'

import { apiFetch } from '../lib/config'

const KNOWN_AGENT_IDS = new Set<string>(['you', 'builder', 'reviewer', 'architect', 'tester', 'retro'])

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
}

interface BackendOption {
  id: string
  label: string
  description?: string
}

function toAgentId(raw: string): AgentId {
  if (raw === 'human') return 'you'
  if (KNOWN_AGENT_IDS.has(raw)) return raw as AgentId
  return 'builder'
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
    pinned: row.type === 'decision',
    ack: ackedBy.length > 0,
    readByAgent,
  }

  if (row.status) m.status = row.status as Message['status']
  if (options) m.options = options

  if (row.type === 'artifact' && row.artifact_path) {
    m.artifact = basename(row.artifact_path)
    if (row.artifact_type) m.atype = row.artifact_type as Message['atype']
  }

  return m
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

export async function apiDelete(messageId: string): Promise<boolean> {
  try {
    const r = await apiFetch(`/comms/delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message_id: messageId }),
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

/** Read a feature's STATE.json (filesystem) — current stage + conversation count. */
export async function fetchFeatureState(projectPath: string, featureId: string): Promise<FeatureState | null> {
  try {
    const raw = await readFile(`${projectPath}/pathly/plans/${featureId}/STATE.json`)
    if (!raw) return null
    return JSON.parse(raw) as FeatureState
  } catch {
    return null
  }
}

/** A feature is blocked when its feedback/ folder holds an open failure/question file. */
export async function featureBlocked(projectPath: string, featureId: string): Promise<boolean> {
  try {
    const files = await listDir(`${projectPath}/pathly/plans/${featureId}/feedback`).catch(() => [] as string[])
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
    const raw = await readFile(`${projectPath}/pathly/plans/${featureId}/EVENTS.jsonl`)
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
