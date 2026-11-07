import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import type { IPty } from 'node-pty'

vi.mock('./log', () => ({ slog: vi.fn() }))

import { slog } from './log'
import { attachStartupHandling } from './promptInjector'

// The trust screen as the installed claude prints it (see the fixture's `# source:` line).
// A person who captures the screen on their own claude replaces only the file.
const FIXTURE = readFileSync(join(__dirname, '__tests__', 'claude-trust-screen.txt'), 'utf-8')
const TRUST_SCREEN = FIXTURE.split('\n').filter((l) => !l.startsWith('#')).join('\r\n')

const CHIEF_TAB = 'chief-0123456789ab'
const PROMPT = 'You are the chief.'
const PASTE = '\x1b[200~' + PROMPT + '\x1b[201~'

function fakePty() {
  const listeners = new Set<(d: string) => void>()
  const writes: string[] = []
  const pty = {
    onData: (fn: (d: string) => void) => {
      listeners.add(fn)
      return { dispose: () => { listeners.delete(fn) } }
    },
    write: vi.fn((d: string) => { writes.push(d) }),
  }
  const emit = (d: string): void => { for (const l of [...listeners]) l(d) }
  return { pty: pty as unknown as IPty, emit, writes }
}

const pastes = (writes: string[]): number => writes.filter((w) => w.startsWith('\x1b[200~')).length
const gateLogs = (): string[] =>
  vi.mocked(slog).mock.calls.filter((c) => c[0] === 'gate').map((c) => String(c[2]))

describe('attachStartupHandling', () => {
  beforeEach(() => { vi.useFakeTimers(); vi.mocked(slog).mockClear() })
  afterEach(() => { vi.useRealTimers() })

  it('reads a fixture that names its source', () => {
    expect(FIXTURE.startsWith('# source:')).toBe(true)
    expect(TRUST_SCREEN).toMatch(/Is this a project you created or one you trust/)
  })

  it('answers the trust screen on a chief tab, then pastes only after the ready prompt', () => {
    const { pty, emit, writes } = fakePty()
    attachStartupHandling(pty, { tabId: CHIEF_TAB, initialInput: PROMPT, headlessEngine: false })

    emit(TRUST_SCREEN)
    vi.advanceTimersByTime(1500)
    // The fixture's cursor sits on "No, exit": move to "Yes, I trust this folder", then Enter.
    expect(writes).toEqual(['\x1b[B\r'])
    expect(writes[0].endsWith('\r')).toBe(true)

    // The screen re-rendering with the new selection is not the ready prompt.
    emit('\r No, exit\r❯Yes, I trust this folder\r\r\n')
    vi.advanceTimersByTime(30000)
    expect(pastes(writes)).toBe(0)

    emit('──────\r\n> ')
    expect(writes.filter((w) => w === PASTE)).toHaveLength(1)
    vi.advanceTimersByTime(6000)
    expect(writes.at(-1)).toBe('\r')
    emit('> ')
    vi.advanceTimersByTime(60000)
    expect(pastes(writes)).toBe(1)
    expect(gateLogs().some((m) => m.includes('folder-trust'))).toBe(true)
  })

  it('answers the screen as the PTY really sends it (columns as cursor moves, no spaces)', () => {
    const { pty, emit, writes } = fakePty()
    attachStartupHandling(pty, { tabId: CHIEF_TAB, initialInput: PROMPT, headlessEngine: false })
    emit(TRUST_SCREEN.replace(/ /g, '\x1b[5G'))
    vi.advanceTimersByTime(1500)
    expect(writes).toEqual(['\x1b[B\r'])
  })

  it('pastes on the measured ready prompt (U+276F and a no-break space)', () => {
    const { pty, emit, writes } = fakePty()
    attachStartupHandling(pty, { tabId: CHIEF_TAB, initialInput: PROMPT, headlessEngine: false })
    emit('────\r\n❯ \x1b[7m \x1b[27m\r\n────')
    expect(writes).toEqual([PASTE])
  })

  it('never pastes into a chief tab on the 5-second fallback, and logs the wait', () => {
    const { pty, emit, writes } = fakePty()
    attachStartupHandling(pty, { tabId: CHIEF_TAB, initialInput: PROMPT, headlessEngine: false })
    emit('Claude Code is starting…')
    vi.advanceTimersByTime(60000)
    expect(writes).toEqual([])
    expect(gateLogs().some((m) => m.includes('no ready prompt yet'))).toBe(true)
  })

  it('still pastes into a non-chief interactive tab after 5 seconds', () => {
    const { pty, writes } = fakePty()
    attachStartupHandling(pty, { tabId: 'tab-7', initialInput: PROMPT, headlessEngine: false })
    vi.advanceTimersByTime(4999)
    expect(writes).toEqual([])
    vi.advanceTimersByTime(1)
    expect(writes).toEqual([PASTE])
    expect(gateLogs().some((m) => m.includes('no ready prompt yet'))).toBe(true)
  })

  it('treats only chief-<12 hex> as a chief tab', () => {
    for (const tabId of ['chief-1', 'chief-0123456789abc', 'xchief-0123456789ab', 'chief-0123456789AB']) {
      const { pty, writes } = fakePty()
      attachStartupHandling(pty, { tabId, initialInput: PROMPT, headlessEngine: false })
      vi.advanceTimersByTime(5000)
      expect(writes).toEqual([PASTE])
    }
  })

  it('still matches the old wording and answers it with Enter', () => {
    const { pty, emit, writes } = fakePty()
    attachStartupHandling(pty, { tabId: CHIEF_TAB, initialInput: PROMPT, headlessEngine: false })
    emit('Do you trust the files in this folder?\r\n❯ 1. Yes, proceed\r\n  2. No, exit\r\n')
    vi.advanceTimersByTime(1500)
    expect(writes).toEqual(['\r'])
    emit('> ')
    expect(writes).toEqual(['\r', PASTE])
  })

  it('answers the issue-quoted wording, cursor on Yes, with Enter', () => {
    const { pty, emit, writes } = fakePty()
    attachStartupHandling(pty, { tabId: 'run-1', headlessEngine: true })
    emit('Quick safety check: Is this a project you created or one you trust?\r\n'
      + '❯ 1. Yes, I trust this folder  2. No, exit · Enter to confirm · Esc to cancel')
    vi.advanceTimersByTime(1500)
    expect(writes).toEqual(['\r'])
  })

  it('answers the current wording once on a headless tab', () => {
    const { pty, emit, writes } = fakePty()
    attachStartupHandling(pty, { tabId: 'run-2', headlessEngine: true })
    emit(TRUST_SCREEN)
    vi.advanceTimersByTime(1500)
    emit(TRUST_SCREEN)
    vi.advanceTimersByTime(1500)
    expect(writes).toEqual(['\x1b[B\r'])
  })

  it('answers the old wording on a headless tab', () => {
    const { pty, emit, writes } = fakePty()
    attachStartupHandling(pty, { tabId: 'run-3', headlessEngine: true })
    emit('Do you trust the files in this folder?')
    vi.advanceTimersByTime(1500)
    expect(writes).toEqual(['\r'])
  })
})
