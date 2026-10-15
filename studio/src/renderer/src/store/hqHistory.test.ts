import { describe, expect, it } from 'vitest'
import type { Message } from './chatStore'
import { adoptInto, migrateHqHistory, restorable, sessionTitle, UNASSIGNED, upsertSession, type HqSession } from './hqHistory'

const user = (id: string, content: string): Message => ({ id, role: 'user', content, status: 'done' })
const bot = (id: string, content: string, status: Message['status'] = 'done'): Message =>
  ({ id, role: 'assistant', content, status })

describe('sessionTitle', () => {
  it('is the first question on one line', () => {
    expect(sessionTitle([user('1', '  what needs\nmy attention? ')])).toBe('what needs my attention?')
  })
  it('caps long titles at 60 characters', () => {
    expect(sessionTitle([user('1', 'x'.repeat(80))])).toHaveLength(58)
  })
  it('falls back for a chat with no question', () => {
    expect(sessionTitle([bot('1', 'hi')])).toBe('New chat')
  })
})

describe('upsertSession', () => {
  const chat = [user('1', 'status?'), bot('2', 'all good')]

  it('never saves an empty chat', () => {
    expect(upsertSession([], 'a', [], 1)).toEqual([])
  })

  it('puts the saved chat first with a title', () => {
    const old: HqSession = { id: 'b', title: 'old', messages: chat, updatedAt: 1 }
    const out = upsertSession([old], 'a', chat, 5)
    expect(out.map((s) => s.id)).toEqual(['a', 'b'])
    expect(out[0]).toMatchObject({ title: 'status?', updatedAt: 5 })
  })

  it('keeps an unchanged chat in place (opening it does not reorder history)', () => {
    const sessions: HqSession[] = [
      { id: 'b', title: 'b', messages: [user('9', 'b?')], updatedAt: 9 },
      { id: 'a', title: 'a', messages: chat, updatedAt: 1 },
    ]
    expect(upsertSession(sessions, 'a', [...chat], 50)).toBe(sessions)
  })

  it('moves a chat with a new message to the top', () => {
    const sessions: HqSession[] = [
      { id: 'b', title: 'b', messages: [user('9', 'b?')], updatedAt: 9 },
      { id: 'a', title: 'a', messages: chat, updatedAt: 1 },
    ]
    const out = upsertSession(sessions, 'a', [...chat, user('3', 'more?')], 50)
    expect(out.map((s) => s.id)).toEqual(['a', 'b'])
    expect(out[0].messages).toHaveLength(3)
  })

  it('drops the oldest chats past the cap', () => {
    const many = Array.from({ length: 3 }, (_, i) => ({ id: `s${i}`, title: '', messages: chat, updatedAt: i }))
    expect(upsertSession(many, 'new', chat, 99, 3).map((s) => s.id)).toEqual(['new', 's0', 's1'])
  })
})

describe('restorable', () => {
  it('closes out an answer cut off mid-stream', () => {
    const out = restorable([user('1', 'q?'), bot('2', 'partial', 'streaming'), bot('3', '', 'streaming')])
    expect(out[1]).toMatchObject({ status: 'done', content: 'partial' })
    expect(out[2]).toMatchObject({ status: 'done', content: '_(answer interrupted)_' })
    expect(out[0]).toEqual(user('1', 'q?'))
  })
})

describe('adoptInto (pre-per-project chats)', () => {
  const s = (id: string, t: number): HqSession => ({ id, title: id, messages: [user(`${id}-u`, id)], updatedAt: t })

  it('a project with no chats takes the unassigned chats and their open chat', () => {
    const out = adoptInto(undefined, { currentId: 'old', sessions: [s('old', 5)] })
    expect(out).toEqual({ currentId: 'old', sessions: [s('old', 5)] })
  })

  it('merges into a project that has chats, newest first, keeping its open chat', () => {
    const out = adoptInto({ currentId: 'mine', sessions: [s('mine', 9)] }, { currentId: 'old', sessions: [s('old', 5)] })
    expect(out.currentId).toBe('mine')
    expect(out.sessions.map((x) => x.id)).toEqual(['mine', 'old'])
  })
})

describe('migrateHqHistory (saved-data upgrades)', () => {
  const s = (id: string, t: number): HqSession => ({ id, title: id, messages: [user(`${id}-u`, id)], updatedAt: t })

  it('v0: one global history becomes the bucket the first project adopts', () => {
    expect(migrateHqHistory({ currentId: 'c', sessions: [s('c', 1)] }, 0))
      .toEqual({ byProject: { [UNASSIGNED]: { currentId: 'c', sessions: [s('c', 1)] } } })
    expect(migrateHqHistory({ currentId: 'c', sessions: [] }, 0)).toEqual({ byProject: {} })
  })

  it('v1: chats stored under the key "undefined" move to the unassigned bucket', () => {
    const out = migrateHqHistory({ byProject: { undefined: { currentId: 'x', sessions: [s('x', 3)] }, '/p': { currentId: 'p', sessions: [] } } }, 1)
    expect(Object.keys(out.byProject).sort()).toEqual(['/p', UNASSIGNED].sort())
    expect(out.byProject[UNASSIGNED].sessions.map((z) => z.id)).toEqual(['x'])
  })

  it('v2 data passes through untouched', () => {
    const data = { byProject: { '/p': { currentId: 'p', sessions: [s('p', 1)] } } }
    expect(migrateHqHistory(data, 2)).toEqual(data)
  })
})
