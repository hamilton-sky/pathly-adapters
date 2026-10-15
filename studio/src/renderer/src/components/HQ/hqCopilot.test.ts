import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('../../lib/config', () => ({ apiFetch: vi.fn() }))

import { apiFetch } from '../../lib/config'
import { fetchHqTurn, localGeneration, resolveHqBoard, shouldUseHqCopilot } from './hqCopilot'

const mockedFetch = vi.mocked(apiFetch)

describe('shouldUseHqCopilot', () => {
  it('never answers without an open board', () => {
    expect(shouldUseHqCopilot(false, 'what needs my attention?', null)).toBe(false)
  })

  it('with actions enabled, a plain (not confident) match is the operator\'s', () => {
    expect(shouldUseHqCopilot(true, 'pause the builder', 0.5)).toBe(false)
    expect(shouldUseHqCopilot(true, 'pause the builder', 0.5, true)).toBe(true)
    expect(shouldUseHqCopilot(true, 'pause the builder', 0.7, true)).toBe(false)
  })

  it('answers when no skill matched', () => {
    expect(shouldUseHqCopilot(true, 'tell me about goal two', null)).toBe(true)
    expect(shouldUseHqCopilot(true, 'hello', 0.2)).toBe(true)
  })

  it('keeps questions that loosely match a skill', () => {
    expect(shouldUseHqCopilot(true, 'what needs my attention?', 0.5)).toBe(true)
    expect(shouldUseHqCopilot(true, 'Is the builder running', 0.45)).toBe(true)
  })

  it('leaves skill requests to the skill matcher', () => {
    expect(shouldUseHqCopilot(true, 'build the feature', 0.5)).toBe(false)
    expect(shouldUseHqCopilot(true, 'what does review do?', 0.8)).toBe(false)
  })
})

describe('fetchHqTurn', () => {
  afterEach(() => { mockedFetch.mockReset() })

  it('maps the server turn', async () => {
    const manifest = { board: 'board-a', tokens_est: 900, budget: 6000, sections: [], model: 'qwen3-8b', eligible_model: true, unavailable: false }
    mockedFetch.mockResolvedValue(new Response(JSON.stringify({
      redirect: null, system_prompt: 'SYS', prompt: '<pathly-context>…</pathly-context>\n\nq?', manifest, context_tokens: 16000,
    })))
    const turn = await fetchHqTurn('q?', 'board-a', '/proj', 'qwen3-8b', ['questions', 'goals'])
    expect(turn).toEqual({ redirect: null, systemPrompt: 'SYS', prompt: '<pathly-context>…</pathly-context>\n\nq?', manifest, contextTokens: 16000, tools: [], actions: [] })
    const [path, init] = mockedFetch.mock.calls[0]
    expect(path).toBe('/hq/prompt')
    expect(JSON.parse(init?.body as string)).toEqual({
      message: 'q?', board: 'board-a', project_root: '/proj', model: 'qwen3-8b', sections: ['questions', 'goals'],
    })
  })

  it('carries the ticked operator actions and returns the offered tools', async () => {
    const tools = [{ name: 'pause_run', description: 'd', parameters: {} }]
    mockedFetch.mockResolvedValue(new Response(JSON.stringify({
      redirect: null, system_prompt: 'OP', prompt: 'p', manifest: null, context_tokens: 16100, tools, actions: ['pause_run'],
    })))
    const turn = await fetchHqTurn('pause it', 'b', null, 'qwen3-8b', [], ['pause_run'])
    expect(JSON.parse(mockedFetch.mock.calls[0][1]?.body as string).enabled_actions).toEqual(['pause_run'])
    expect([turn.tools, turn.actions]).toEqual([tools, ['pause_run']])
  })

  it('passes a redirect through', async () => {
    mockedFetch.mockResolvedValue(new Response(JSON.stringify({
      redirect: 'ask the chief', system_prompt: null, prompt: null, manifest: null, context_tokens: 0,
    })))
    const turn = await fetchHqTurn('stop the run', 'board-a', null, 'phi-4-mini')
    expect(turn.redirect).toBe('ask the chief')
    expect(turn.prompt).toBeNull()
  })

  it('degrades to an unavailable turn on a server error or network failure', async () => {
    mockedFetch.mockResolvedValueOnce(new Response('boom', { status: 500 }))
    const a = await fetchHqTurn('q?', 'b', null, 'phi-4-mini')
    expect(a).toMatchObject({ redirect: null, systemPrompt: null, prompt: null, contextTokens: 0 })
    expect(a.manifest?.unavailable).toBe(true)
    expect(a.manifest?.board).toBe('b')

    mockedFetch.mockRejectedValueOnce(new Error('offline'))
    const b = await fetchHqTurn('q?', 'b', null, 'phi-4-mini')
    expect(b.manifest?.unavailable).toBe(true)
  })
})

describe('resolveHqBoard — the board the user is looking at', () => {
  it('the main board tab wins when its section is open', () => {
    expect(resolveHqBoard('other', '/p', { mainFeature: 'board-differ', openFeatures: ['x', 'board-differ'] }))
      .toEqual({ board: 'board-differ', projectRoot: '/p' })
  })

  it('else any open feature board, before the open topic', () => {
    expect(resolveHqBoard('other', '/p', { mainFeature: 'closed', openFeatures: ['x'] })?.board).toBe('x')
  })

  it('with no board open: the open topic, then the last main board', () => {
    expect(resolveHqBoard('topic', '/p', { mainFeature: 'main', openFeatures: [] })?.board).toBe('topic')
    expect(resolveHqBoard(null, '/p', { mainFeature: 'main', openFeatures: [] })?.board).toBe('main')
  })

  it('skips an open topic that is no board (a goal run slug)', () => {
    const boards = { mainFeature: 'main', openFeatures: [], knownFeatures: ['main', 'board-differ'] }
    expect(resolveHqBoard('goal-unified-gateway-engine-6303b11e', '/p', boards)?.board).toBe('main')
    expect(resolveHqBoard('board-differ', '/p', boards)?.board).toBe('board-differ')
  })

  it('no board at all → no copilot', () => {
    expect(resolveHqBoard(null, '/p', { mainFeature: null, openFeatures: [] })).toBeNull()
  })
})

describe('localGeneration (the Fast/Deep switch)', () => {
  it('Deep: reasons with a capped budget and shows the reasoning', () => {
    expect(localGeneration('deep')).toEqual({ maxTokens: 2048, thoughtBudget: 768, showReasoning: true })
  })

  it('Fast: no reasoning at all (thoughtBudget 0, not "unset")', () => {
    expect(localGeneration('fast')).toEqual({ maxTokens: 1024, thoughtBudget: 0 })
  })

  it("carries a board turn's context size", () => {
    expect(localGeneration('fast', 16000)).toMatchObject({ contextSize: 16000, thoughtBudget: 0 })
  })
})
