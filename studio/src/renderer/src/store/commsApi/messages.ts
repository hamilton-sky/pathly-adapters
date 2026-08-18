// Board message CRUD — read a board, post to it, and act on a single message
// (answer, acknowledge, re-scope, edit, delete).

import type { Message, MessageType, Stage, BoardScope } from '../../components/CommandCenter/types'
import { apiFetch } from '../../lib/config'
import { type CommsRow, rowToMessage } from './rows'

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
