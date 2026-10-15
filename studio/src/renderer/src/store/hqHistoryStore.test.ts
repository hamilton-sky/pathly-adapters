import { beforeEach, describe, expect, it } from 'vitest'
import type { Message } from './chatStore'
import { useHqHistoryStore } from './hqHistoryStore'
import { UNASSIGNED } from './hqHistory'

const chat = (q: string): Message[] => [
  { id: `${q}-u`, role: 'user', content: q, status: 'done' },
  { id: `${q}-a`, role: 'assistant', content: `answer to ${q}`, status: 'done' },
]

describe('hqHistoryStore — one history per project', () => {
  beforeEach(() => { useHqHistoryStore.setState({ byProject: {} }) })

  it('keeps each project’s chats separate', () => {
    const s = useHqHistoryStore.getState()
    s.saveCurrent('/proj/a', chat('a?'))
    s.saveCurrent('/proj/b', chat('b?'))
    const { byProject } = useHqHistoryStore.getState()
    expect(byProject['/proj/a'].sessions.map((x) => x.title)).toEqual(['a?'])
    expect(byProject['/proj/b'].sessions.map((x) => x.title)).toEqual(['b?'])
  })

  it('New chat starts a new current chat in that project only', () => {
    const s = useHqHistoryStore.getState()
    s.saveCurrent('/proj/a', chat('a1?'))
    const bBefore = s.ensure('/proj/b').currentId
    s.startNew('/proj/a')
    s.saveCurrent('/proj/a', chat('a2?'))
    const { byProject } = useHqHistoryStore.getState()
    expect(byProject['/proj/a'].sessions.map((x) => x.title)).toEqual(['a2?', 'a1?'])
    expect(byProject['/proj/b'].currentId).toBe(bBefore)
  })

  it('opening a chat only finds chats of that project', () => {
    const s = useHqHistoryStore.getState()
    s.saveCurrent('/proj/a', chat('a?'))
    const id = useHqHistoryStore.getState().byProject['/proj/a'].currentId
    expect(s.open('/proj/b', id)).toBeNull()
    expect(s.open('/proj/a', id)?.title).toBe('a?')
  })

  it('the first project to open adopts chats saved before per-project history', () => {
    useHqHistoryStore.setState({ byProject: { [UNASSIGNED]: { currentId: 'old', sessions: [{ id: 'old', title: 'old?', messages: chat('old?'), updatedAt: 1 }] } } })
    useHqHistoryStore.getState().adoptUnassigned('/proj/a')
    const { byProject } = useHqHistoryStore.getState()
    expect(byProject[UNASSIGNED]).toBeUndefined()
    expect(byProject['/proj/a'].currentId).toBe('old')
    useHqHistoryStore.getState().adoptUnassigned('/proj/b')
    expect(useHqHistoryStore.getState().byProject['/proj/b']).toBeUndefined()
  })
})
