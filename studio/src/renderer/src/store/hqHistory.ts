// Pure helpers for HQ chat history (store: hqHistoryStore.ts, wiring: HQ/useHqHistory.ts).
import type { Message } from './chatStore'

export interface HqSession {
  id: string
  title: string
  messages: Message[]
  updatedAt: number
}

/** Saved chats kept; the oldest drop off first. */
export const MAX_HQ_SESSIONS = 30

/** The chat's first question, on one line, at most 60 characters. */
export function sessionTitle(messages: Message[]): string {
  const first = messages.find((m) => m.role === 'user' && m.content.trim())
  const title = (first?.content ?? 'New chat').replace(/\s+/g, ' ').trim()
  return title.length > 60 ? `${title.slice(0, 57)}…` : title
}

function sameConversation(a: Message[], b: Message[]): boolean {
  if (a.length !== b.length) return false
  const x = a[a.length - 1]
  const y = b[b.length - 1]
  return !x || (x.id === y.id && x.content === y.content && x.status === y.status)
}

/** Save *messages* as chat *id*, newest first, capped at *max*. An empty chat is
 *  never saved, and re-saving an unchanged one keeps its place — so opening an
 *  old chat does not reorder the history. */
export function upsertSession(
  sessions: HqSession[],
  id: string,
  messages: Message[],
  now: number,
  max = MAX_HQ_SESSIONS,
): HqSession[] {
  if (messages.length === 0) return sessions
  const existing = sessions.find((s) => s.id === id)
  if (existing && sameConversation(existing.messages, messages)) return sessions
  const updated: HqSession = { id, title: sessionTitle(messages), messages, updatedAt: now }
  return [updated, ...sessions.filter((s) => s.id !== id)].slice(0, max)
}

/** A saved chat as it should reopen: an answer cut off mid-stream (reload, quit)
 *  is closed out instead of showing thinking dots forever. */
export function restorable(messages: Message[]): Message[] {
  return messages.map((m) =>
    m.status === 'streaming'
      ? { ...m, status: 'done' as const, content: m.content || '_(answer interrupted)_' }
      : m,
  )
}

/** One project's HQ chats: the chat on screen and the saved list. */
export interface ProjectHistory {
  currentId: string
  sessions: HqSession[]
}

/** Bucket for chats saved before history was per-project (persist v0); the
 *  first project HQ opens adopts them, so nothing saved earlier is lost. */
export const UNASSIGNED = '(unassigned)'

/** Fold *unassigned* chats into a project's history, newest first, capped. A
 *  project with no chats of its own also takes over the unassigned current chat. */
export function adoptInto(
  target: ProjectHistory | undefined,
  unassigned: ProjectHistory,
  max = MAX_HQ_SESSIONS,
): ProjectHistory {
  const own = target?.sessions ?? []
  const sessions = [...own, ...unassigned.sessions]
    .sort((a, b) => b.updatedAt - a.updatedAt)
    .slice(0, max)
  const currentId = target && own.length > 0 ? target.currentId : unassigned.currentId
  return { currentId, sessions }
}

/** Saved-history upgrades (zustand persist `migrate`).
 *  v0 → v1: one global history becomes the unassigned bucket the first project adopts.
 *  v1 → v2: a hot reload during the v1 rollout saved chats under the key
 *  "undefined"; they move to the unassigned bucket so they are adopted too. */
export function migrateHqHistory(persisted: unknown, version: number): { byProject: Record<string, ProjectHistory> } {
  const p = (persisted ?? {}) as { currentId?: string; sessions?: HqSession[]; byProject?: Record<string, ProjectHistory> }
  if (version < 1) {
    return p.sessions?.length
      ? { byProject: { [UNASSIGNED]: { currentId: p.currentId ?? crypto.randomUUID(), sessions: p.sessions } } }
      : { byProject: {} }
  }
  const { undefined: stray, ...byProject } = p.byProject ?? {}
  if (version < 2 && stray) {
    const parked = byProject[UNASSIGNED]
    byProject[UNASSIGNED] = parked ? adoptInto(parked, stray) : stray
  }
  return { byProject }
}
