// The FSM decision gate — resolving a board question into a runner decision, and reading
// back what the runner is waiting on.

import { apiFetch } from '../../lib/config'

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
