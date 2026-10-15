// HQ operator turn (pathly/features/local-operator): when the composer has
// actions ticked and the built-in runtime answers, the model is offered those
// actions as functions; what it calls comes back as PROPOSALS, which the server
// checks (POST /hq/actions/check) and which attach to the answer as confirm
// cards. Nothing runs here — a card runs on its Run click (actionCards.ts).
import { apiFetch } from '../../lib/config'
import { askLlm, askLlmWithTools } from '../../lib/llmBridge'
import { useChatStore, type HqActionCard } from '../../store/chatStore'
import { useHqActionsStore } from '../../store/hqActionsStore'
import type { HqTurn, LocalGeneration } from './hqCopilot'

/** The actions the next question may propose: the composer's ticked ones, on
 *  the built-in runtime only (Ollama keeps HQ read-only — ticket 01). */
export function operatorActions(builtIn: boolean): string[] {
  return builtIn ? useHqActionsStore.getState().enabled : []
}

/** Shown when the model only proposed (no prose of its own). */
export const PROPOSED_ONLY_NOTE = 'Proposed below — Run or Cancel each.'

export interface OperatorTurn {
  tools: HqToolSpec[]
  actions: string[]
  board: string
  projectRoot: string | null
  messageId: string
}

/** The operator side of an HQ turn, or null for a read-only one. */
export function operatorTurn(
  hq: HqTurn | null,
  hqBoard: { board: string; projectRoot: string | null } | null,
  messageId: string,
): OperatorTurn | null {
  if (!hq?.tools.length || !hqBoard) return null
  return { tools: hq.tools, actions: hq.actions, board: hqBoard.board, projectRoot: hqBoard.projectRoot, messageId }
}

interface CheckResponse {
  cards: Omit<HqActionCard, 'board' | 'projectRoot'>[]
  dropped: { name: string; reason: string }[]
}

/** Proposals → cards via the server (it drops what isn't enabled and resolves
 *  targets). A failed check becomes no cards: nothing can run unchecked. */
export async function checkProposals(op: OperatorTurn, proposals: HqToolProposal[]): Promise<HqActionCard[]> {
  try {
    const res = await apiFetch('/hq/actions/check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        board: op.board, project_root: op.projectRoot ?? undefined, enabled_actions: op.actions, proposals,
      }),
    })
    if (!res.ok) return []
    const d = await res.json() as CheckResponse
    return d.cards.map((c) => ({ ...c, board: op.board, projectRoot: op.projectRoot }))
  } catch {
    return []
  }
}

/** Ask the built-in model. With an operator turn, attach its proposals to the
 *  answer as confirm cards; returns how many. */
export async function askLocalTurn(
  prompt: string,
  systemPrompt: string,
  onChunk: (text: string) => void,
  gen: LocalGeneration,
  op: OperatorTurn | null,
): Promise<number> {
  if (!op) {
    await askLlm(prompt, systemPrompt, onChunk, gen)
    return 0
  }
  const { proposals } = await askLlmWithTools(prompt, systemPrompt, onChunk, { ...gen, tools: op.tools })
  if (!proposals.length) return 0
  const cards = await checkProposals(op, proposals)
  if (cards.length) useChatStore.getState().updateMessage(op.messageId, { actionCards: cards })
  return cards.length
}
