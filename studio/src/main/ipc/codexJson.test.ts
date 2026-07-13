import { describe, it, expect } from 'vitest'
import { parseCodexResult } from './codexJson'

// Mirrors tests/test_runner.py's codex token-capture cases so the TS one-shot path and the
// Python supervisor path agree on the (defensive, version-varying) codex `exec --json` shapes.

/** Wrap JSONL as a PTY would: join with \r\n and hard-wrap at `width` cols to prove the parser
 *  is robust to the terminal's column wrapping (the real bug surface). */
function ptyWrap(jsonl: string, width = 40): string {
  const oneLine = jsonl.replace(/\n/g, '')
  const out: string[] = []
  for (let i = 0; i < oneLine.length; i += width) out.push(oneLine.slice(i, i + width))
  return out.join('\r\n')
}

describe('parseCodexResult', () => {
  it('captures tokens from a typed token_count event', () => {
    const raw =
      '{"type":"session_start","session_id":"codex-abc"}\n' +
      '{"type":"token_count","input_tokens":1200,"output_tokens":340}\n' +
      '{"type":"agent_message","text":"done"}\n'
    const r = parseCodexResult(raw)
    expect(r?.tokens_in).toBe(1200)
    expect(r?.tokens_out).toBe(340)
    expect(r?.result).toBe('done')
  })

  it('captures a nested usage field (prompt/completion aliases)', () => {
    const r = parseCodexResult('{"usage":{"prompt_tokens":500,"completion_tokens":90}}')
    expect(r?.tokens_in).toBe(500)
    expect(r?.tokens_out).toBe(90)
  })

  it('folds cached input into tokens_in from info.total_token_usage', () => {
    const raw =
      '{"info":{"total_token_usage":{"input_tokens":2000,"cached_input_tokens":300,"output_tokens":150}}}'
    const r = parseCodexResult(raw)
    expect(r?.tokens_in).toBe(2300)
    expect(r?.tokens_out).toBe(150)
  })

  it('keeps the last non-zero usage event', () => {
    const raw =
      '{"usage":{"input_tokens":100,"output_tokens":20}}\n' +
      '{"usage":{"input_tokens":400,"output_tokens":80}}\n'
    const r = parseCodexResult(raw)
    expect(r?.tokens_in).toBe(400)
    expect(r?.tokens_out).toBe(80)
  })

  it('yields zero tokens when there is no usage event', () => {
    const r = parseCodexResult('{"type":"agent_message","text":"hello"}\n')
    expect(r?.tokens_in).toBe(0)
    expect(r?.tokens_out).toBe(0)
    expect(r?.result).toBe('hello')
  })

  it('survives PTY column-wrapping of the JSONL stream', () => {
    const raw =
      '{"type":"token_count","input_tokens":1200,"output_tokens":340}\n' +
      '{"type":"agent_message","text":"a longer diagram result that the terminal will wrap"}\n'
    const r = parseCodexResult(ptyWrap(raw, 24))
    expect(r?.tokens_in).toBe(1200)
    expect(r?.tokens_out).toBe(340)
    expect(r?.result).toBe('a longer diagram result that the terminal will wrap')
  })

  it('returns null when the process produced nothing', () => {
    expect(parseCodexResult('')).toBeNull()
    expect(parseCodexResult('   \r\n  ')).toBeNull()
  })
})
