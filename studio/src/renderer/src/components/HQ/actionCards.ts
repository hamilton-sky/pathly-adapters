// Run / Cancel for HQ operator confirm cards (pathly/features/local-operator).
// Nothing runs without the user's click: Run asks the server to revalidate and
// execute (POST /hq/actions/run — a changed board makes the card `stale`), and
// a Studio-run action (diagrams) runs here once approved, then is reported for
// the audit log. Cancel makes no request at all.
import { apiFetch } from '../../lib/config'
import { useChatStore, type HqActionCard, type HqActionStatus } from '../../store/chatStore'
import { runStudioAction } from './studioActions'

function patchCard(messageId: string, cardId: string, patch: Partial<HqActionCard>): void {
  const { messages, updateMessage } = useChatStore.getState()
  const cards = messages.find((m) => m.id === messageId)?.actionCards
  if (!cards) return
  updateMessage(messageId, { actionCards: cards.map((c) => (c.id === cardId ? { ...c, ...patch } : c)) })
}

/** Cards run in order: one may run only when every earlier card has settled. */
export function canRun(cards: HqActionCard[], index: number): boolean {
  return cards[index]?.status === 'proposed'
    && cards.slice(0, index).every((c) => c.status !== 'proposed' && c.status !== 'running')
}

export function cancelActionCard(messageId: string, card: HqActionCard): void {
  if (card.status !== 'proposed') return
  patchCard(messageId, card.id, { status: 'cancelled', summary: 'Cancelled — nothing ran' })
}

interface RunResponse {
  status: HqActionStatus | 'approved'
  summary: string
  target?: Record<string, unknown>
}

async function post(path: string, body: unknown): Promise<Response> {
  return apiFetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
}

async function reportStudioRun(card: HqActionCard, target: Record<string, unknown>, ok: boolean, summary: string): Promise<void> {
  try {
    await post('/hq/actions/report', { board: card.board, name: card.name, target, ok, summary })
  } catch {
    /* the action ran; a missed audit line is logged server-side when it can be */
  }
}

/** The Run click. Settles the card as done / failed / stale / unavailable. */
export async function runActionCard(messageId: string, card: HqActionCard): Promise<void> {
  if (card.status !== 'proposed') return
  patchCard(messageId, card.id, { status: 'running', summary: undefined })
  let d: RunResponse
  try {
    const res = await post('/hq/actions/run', {
      board: card.board,
      project_root: card.projectRoot ?? undefined,
      name: card.name,
      args: card.args,
      fingerprint: card.fingerprint,
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    d = await res.json() as RunResponse
  } catch (err) {
    const why = err instanceof Error ? err.message : String(err)
    patchCard(messageId, card.id, { status: 'failed', summary: `Failed: server unreachable (${why})` })
    return
  }
  if (d.status !== 'approved') {
    patchCard(messageId, card.id, { status: d.status, summary: d.summary })
    return
  }
  const target = d.target ?? {}
  const outcome = await runStudioAction(card.name, target, { board: card.board, projectRoot: card.projectRoot })
  await reportStudioRun(card, target, outcome.ok, outcome.summary)
  patchCard(messageId, card.id, { status: outcome.ok ? 'done' : 'failed', summary: outcome.summary })
}
