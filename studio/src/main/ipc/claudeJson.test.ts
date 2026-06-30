import { describe, it, expect } from 'vitest'
import {
  feedStreamJson,
  newStreamJsonState,
  parseClaudeJsonResult,
  streamToolLabel,
} from './claudeJson'

// One claude stream-json event line (newline-terminated, as claude emits it).
function ev(o: unknown): string {
  return JSON.stringify(o) + '\n'
}

// Simulate the PTY wrapping a program's output at `cols` columns by inserting \r\n — this is
// the exact hazard the renderer must survive (real CR/LF mid-object, even mid-escape).
function ptyWrap(s: string, cols = 80): string {
  let out = ''
  for (let i = 0; i < s.length; i += cols) out += s.slice(i, i + cols) + '\r\n'
  return out
}

function feedAll(chunks: string[]): { emitted: string; state: ReturnType<typeof newStreamJsonState> } {
  const state = newStreamJsonState()
  let emitted = ''
  for (const c of chunks) feedStreamJson(state, c, (t) => { emitted += t })
  return { emitted, state }
}

describe('streamToolLabel', () => {
  it('uses the file basename for file tools', () => {
    expect(streamToolLabel({ name: 'Edit', input: { file_path: 'C:/proj/src/app.ts' } })).toBe('Edit(app.ts)')
  })
  it('uses the command for Bash', () => {
    expect(streamToolLabel({ name: 'Bash', input: { command: 'npm test' } })).toBe('Bash(npm test)')
  })
  it('falls back to the bare tool name with no usable input', () => {
    expect(streamToolLabel({ name: 'TodoWrite' })).toBe('TodoWrite')
  })
})

describe('feedStreamJson', () => {
  it('renders assistant text + tool_use lines and captures the result event', () => {
    const stream =
      ev({ type: 'system', subtype: 'init' }) +
      ev({ type: 'assistant', message: { content: [{ type: 'text', text: 'Working on it' }] } }) +
      ev({ type: 'assistant', message: { content: [{ type: 'tool_use', name: 'Read', input: { file_path: 'a/b/skill.md' } }] } }) +
      ev({ type: 'assistant', message: { content: [{ type: 'tool_use', name: 'Edit', input: { file_path: 'a/b/skill.md' } }] } }) +
      ev({ type: 'result', subtype: 'success', result: 'Done.', total_cost_usd: 0.012, usage: { input_tokens: 100, output_tokens: 50 } })
    const { emitted, state } = feedAll([stream])

    expect(emitted).toContain('Working on it')
    expect(emitted).toContain('⚙ Read(skill.md)')
    expect(emitted).toContain('⚙ Edit(skill.md)')
    expect(emitted).not.toContain('"type"')        // raw JSON must never leak to the terminal
    expect(state.toolUses).toBe(2)
    expect(state.result?.total_cost_usd).toBe(0.012)
    expect(state.result?.usage.input_tokens).toBe(100)
  })

  it('survives PTY column-wrapping (\\r\\n inserted mid-object)', () => {
    const stream =
      ev({ type: 'assistant', message: { content: [{ type: 'text', text: 'A reasonably long line of narration that the PTY will wrap at eighty columns into several physical rows of output' }] } }) +
      ev({ type: 'result', subtype: 'success', result: 'ok', total_cost_usd: 0.5, usage: { input_tokens: 1, output_tokens: 2 } })
    const { emitted, state } = feedAll([ptyWrap(stream, 80)])

    expect(emitted).toContain('A reasonably long line of narration')
    expect(state.result?.total_cost_usd).toBe(0.5)
  })

  it('reassembles an event split across two feed() chunks', () => {
    const line = ev({ type: 'assistant', message: { content: [{ type: 'tool_use', name: 'Write', input: { file_path: 'out.md' } }] } })
    const mid = Math.floor(line.length / 2)
    const { emitted, state } = feedAll([line.slice(0, mid), line.slice(mid)])

    expect(emitted).toContain('⚙ Write(out.md)')
    expect(state.toolUses).toBe(1)
  })

  it('skips non-JSON noise before the event stream', () => {
    const stream =
      'Some startup warning line\n' +
      ev({ type: 'result', subtype: 'success', result: 'x', total_cost_usd: 0.1, usage: { input_tokens: 0, output_tokens: 0 } })
    const { state } = feedAll([stream])

    expect(state.result?.total_cost_usd).toBe(0.1)
  })

  it('preserves escaped content newlines in assistant text', () => {
    const stream = ev({ type: 'assistant', message: { content: [{ type: 'text', text: 'line1\nline2' }] } })
    const { emitted } = feedAll([stream])

    expect(emitted).toContain('line1')
    expect(emitted).toContain('line2')
  })

  it('handles several events arriving in a single chunk', () => {
    const stream = Array.from({ length: 5 }, (_, n) =>
      ev({ type: 'assistant', message: { content: [{ type: 'tool_use', name: 'Read', input: { file_path: `f${n}.ts` } }] } }),
    ).join('')
    const { state } = feedAll([stream])

    expect(state.toolUses).toBe(5)
  })
})

describe('parseClaudeJsonResult', () => {
  it('extracts the result object from buffered, PTY-wrapped JSON output', () => {
    const obj = { type: 'result', subtype: 'success', result: 'hi', total_cost_usd: 0.03, session_id: 'abc', usage: { input_tokens: 5, output_tokens: 7 } }
    const parsed = parseClaudeJsonResult(ptyWrap(JSON.stringify(obj), 40))

    expect(parsed?.total_cost_usd).toBe(0.03)
    expect(parsed?.result).toBe('hi')
  })

  it('returns null when there is no result object', () => {
    expect(parseClaudeJsonResult('just some plain text, no json here')).toBeNull()
  })
})
