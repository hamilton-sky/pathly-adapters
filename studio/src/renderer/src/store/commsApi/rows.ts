// The backend `comms_messages` row shape and its adapter to the UI's Message model.
//
// Everything else in this folder speaks Message; this is the only place that knows what the
// wire actually looks like, so a column rename lands here and nowhere else.

import type { Message, MessageType, Stage, QuestionOption, AgentId } from '../../components/CommandCenter/types'

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
