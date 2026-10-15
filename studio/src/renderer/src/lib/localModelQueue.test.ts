import { describe, expect, it, vi } from 'vitest'
import { runLocal, runningOwner, stopChat } from './localModelQueue'

function deferred(): { promise: Promise<string>; resolve: (v: string) => void } {
  let resolve: (v: string) => void = () => {}
  const promise = new Promise<string>((r) => { resolve = r })
  return { promise, resolve }
}

describe('localModelQueue', () => {
  it('runs one call at a time, in order', async () => {
    const order: string[] = []
    const a = deferred()
    const first = runLocal('background', async () => { order.push('a start'); const v = await a.promise; order.push('a end'); return v }, '')
    const second = runLocal('chat', async () => { order.push('b start'); return 'b' }, '')
    await Promise.resolve()
    expect(order).toEqual(['a start']) // b waits for a
    a.resolve('a')
    expect(await first).toBe('a')
    expect(await second).toBe('b')
    expect(order).toEqual(['a start', 'a end', 'b start'])
  })

  it('Stop drops a waiting chat call without ever running it, and never aborts a summary', async () => {
    const summary = deferred()
    const abort = vi.fn()
    const running = runLocal('background', () => summary.promise, '')
    const chatFn = vi.fn(async () => 'answer')
    const chat = runLocal('chat', chatFn, 'dropped')
    await Promise.resolve()
    expect(runningOwner()).toBe('background')
    stopChat(abort)
    expect(await chat).toBe('dropped')
    expect(abort).not.toHaveBeenCalled()
    summary.resolve('sum')
    expect(await running).toBe('sum')
    await Promise.resolve()
    expect(chatFn).not.toHaveBeenCalled()
  })

  it('Stop aborts a chat call that is running', async () => {
    const answer = deferred()
    const abort = vi.fn(() => answer.resolve('partial'))
    const chat = runLocal('chat', () => answer.promise, '')
    await Promise.resolve(); await Promise.resolve()
    stopChat(abort)
    expect(abort).toHaveBeenCalledTimes(1)
    expect(await chat).toBe('partial')
  })

  it('a failing call does not block the next', async () => {
    const bad = runLocal('background', async () => { throw new Error('boom') }, '')
    await expect(bad).rejects.toThrow('boom')
    expect(await runLocal('chat', async () => 'ok', '')).toBe('ok')
  })
})
