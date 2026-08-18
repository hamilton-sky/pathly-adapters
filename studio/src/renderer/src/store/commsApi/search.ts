// Hybrid search over a board, plus the two relationship edits it feeds: supersede and attach.

import type { Message } from '../../components/CommandCenter/types'
import { apiFetch } from '../../lib/config'
import { type CommsRow, rowToMessage } from './rows'

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
