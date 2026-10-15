import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../../lib/config', () => ({ apiFetch: vi.fn() }))
vi.mock('./studioActions', () => ({ runStudioAction: vi.fn() }))

import { apiFetch } from '../../lib/config'
import { useChatStore, type HqActionCard } from '../../store/chatStore'
import { useHqActionsStore } from '../../store/hqActionsStore'
import { askLocalTurn, operatorActions, operatorTurn, type OperatorTurn } from './hqOperator'
import { canRun, cancelActionCard, runActionCard } from './actionCards'
import { runStudioAction } from './studioActions'

const mockedFetch = vi.mocked(apiFetch)
const json = (body: unknown): Response => new Response(JSON.stringify(body))
const TOOLS: HqToolSpec[] = [{ name: 'pause_run', description: 'd', parameters: { type: 'object' } }]

/** A stubbed built-in model: streams *text* and "calls" *proposals*. */
function stubModel(text: string, proposals: HqToolProposal[]) {
  let onDone: (t: string) => void = () => {}
  const chat = vi.fn(async (..._args: unknown[]) => { onDone(text); return { proposals } })
  Object.assign(window.pathly, {
    llm: {
      chat,
      onToken: () => () => {},
      onDone: (cb: (t: string) => void) => { onDone = cb; return () => {} },
      onError: () => () => {},
    },
  })
  return chat
}

function card(over: Partial<HqActionCard> = {}): HqActionCard {
  return {
    id: 'c1', name: 'pause_run', label: 'Pause a run', risk: ['changes state'], runs_on: 'server',
    args: { run_id: 'r1' }, title: 'Pause run r1', status: 'proposed', fingerprint: 'running',
    board: 'b', projectRoot: '/p', ...over,
  }
}

function seedMessage(cards?: HqActionCard[]): void {
  useChatStore.setState({ messages: [{ id: 'm1', role: 'assistant', content: '', status: 'done', actionCards: cards }] })
}

const OP: OperatorTurn = { tools: TOOLS, actions: ['pause_run'], board: 'b', projectRoot: '/p', messageId: 'm1' }
const paths = (): string[] => mockedFetch.mock.calls.map(([p]) => String(p))

beforeEach(() => { seedMessage() })
afterEach(() => { mockedFetch.mockReset(); vi.mocked(runStudioAction).mockReset(); useHqActionsStore.getState().clear() })

describe('operatorActions — which actions a question may carry', () => {
  it('the ticked actions on the built-in runtime, none on Ollama', () => {
    useHqActionsStore.getState().toggle('pause_run')
    expect(operatorActions(true)).toEqual(['pause_run'])
    expect(operatorActions(false)).toEqual([])
  })

  it('a turn without tools is read-only', () => {
    const hq = { redirect: null, systemPrompt: 's', prompt: 'p', manifest: null, contextTokens: 0, tools: [], actions: [] }
    expect(operatorTurn(hq, { board: 'b', projectRoot: null }, 'm1')).toBeNull()
  })
})

describe('askLocalTurn — the model proposes, nothing runs', () => {
  it('read-only turn: the model gets no tools and no action request is made', async () => {
    const chat = stubModel('answer', [])
    expect(await askLocalTurn('p', 's', () => {}, { maxTokens: 1, thoughtBudget: 0 }, null)).toBe(0)
    expect(chat.mock.calls[0][3]).not.toHaveProperty('tools')
    expect(mockedFetch).not.toHaveBeenCalled()
  })

  it('a proposal becomes a checked card on the answer — never a run', async () => {
    const chat = stubModel('I can pause it.', [{ name: 'pause_run', args: { run_id: 'r1' } }])
    mockedFetch.mockResolvedValue(json({ cards: [card({ board: undefined, projectRoot: undefined })], dropped: [] }))
    expect(await askLocalTurn('p', 's', () => {}, { maxTokens: 1, thoughtBudget: 0 }, OP)).toBe(1)
    expect(chat.mock.calls[0][3]).toMatchObject({ tools: TOOLS })
    expect(paths()).toEqual(['/hq/actions/check'])
    const sent = JSON.parse(mockedFetch.mock.calls[0][1]?.body as string)
    expect(sent).toMatchObject({ board: 'b', enabled_actions: ['pause_run'], proposals: [{ name: 'pause_run' }] })
    const cards = useChatStore.getState().messages[0].actionCards ?? []
    expect(cards.map((c) => [c.status, c.board])).toEqual([['proposed', 'b']])
  })

  it('no proposals → no check, no cards', async () => {
    stubModel('nothing to do', [])
    expect(await askLocalTurn('p', 's', () => {}, { maxTokens: 1, thoughtBudget: 0 }, OP)).toBe(0)
    expect(mockedFetch).not.toHaveBeenCalled()
  })
})

describe('confirm cards — only the Run click acts', () => {
  it('Cancel makes no request and ends as a record', () => {
    const c = card()
    seedMessage([c])
    cancelActionCard('m1', c)
    expect(mockedFetch).not.toHaveBeenCalled()
    expect(useChatStore.getState().messages[0].actionCards?.[0].status).toBe('cancelled')
  })

  it('Run revalidates and executes on the server, then records the result', async () => {
    const c = card()
    seedMessage([c])
    mockedFetch.mockResolvedValue(json({ status: 'done', summary: 'Paused run r1' }))
    await runActionCard('m1', c)
    expect(paths()).toEqual(['/hq/actions/run'])
    expect(JSON.parse(mockedFetch.mock.calls[0][1]?.body as string)).toMatchObject({ name: 'pause_run', fingerprint: 'running' })
    expect(useChatStore.getState().messages[0].actionCards?.[0]).toMatchObject({ status: 'done', summary: 'Paused run r1' })
  })

  it('a stale board ends the card as stale', async () => {
    const c = card()
    seedMessage([c])
    mockedFetch.mockResolvedValue(json({ status: 'stale', summary: 'Not run: the board changed' }))
    await runActionCard('m1', c)
    expect(useChatStore.getState().messages[0].actionCards?.[0].status).toBe('stale')
  })

  it('a Studio-run action runs after approval and is reported for the audit', async () => {
    const c = card({ name: 'diagram_artifact', runs_on: 'studio' })
    seedMessage([c])
    mockedFetch
      .mockResolvedValueOnce(json({ status: 'approved', summary: '', target: { path: '/p/a.md', style: null } }))
      .mockResolvedValueOnce(json({ ok: true }))
    vi.mocked(runStudioAction).mockResolvedValue({ ok: true, summary: 'Diagram agent started' })
    await runActionCard('m1', c)
    expect(runStudioAction).toHaveBeenCalledWith('diagram_artifact', { path: '/p/a.md', style: null }, { board: 'b', projectRoot: '/p' })
    expect(paths()).toEqual(['/hq/actions/run', '/hq/actions/report'])
    expect(useChatStore.getState().messages[0].actionCards?.[0].status).toBe('done')
  })

  it('cards run in order: the second waits for the first to settle', () => {
    const cards = [card({ id: 'a' }), card({ id: 'b' })]
    expect([canRun(cards, 0), canRun(cards, 1)]).toEqual([true, false])
    cards[0] = { ...cards[0], status: 'cancelled' }
    expect(canRun(cards, 1)).toBe(true)
  })
})
