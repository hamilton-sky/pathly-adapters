import { describe, it, expect } from 'vitest'
import { classifyEngineFailure, retryDelayMs, MAX_TRANSIENT_RETRIES } from './engineFailure'

describe('classifyEngineFailure', () => {
  it('classifies a codex "at capacity" turn.failed as transient even on exit 0', () => {
    // The real stream that lost a diagram run: codex reports the failure in its JSON
    // event stream, so exit code alone cannot be trusted.
    const tail =
      '{"type":"error","message":"Selected model is at capacity. Please try a different model."}\n' +
      '{"type":"turn.failed","error":{"message":"Selected model is at capacity. Please try a different model."}}'
    expect(classifyEngineFailure(0, tail)).toBe('transient')
  })

  it('classifies classic rate-limit wording on a non-zero exit as transient', () => {
    expect(classifyEngineFailure(1, 'Error: 429 Too Many Requests')).toBe('transient')
    expect(classifyEngineFailure(1, 'usage limit reached')).toBe('transient')
    expect(classifyEngineFailure(1, 'upstream overloaded, retry')).toBe('transient')
    expect(classifyEngineFailure(1, '503 Service Unavailable')).toBe('transient')
  })

  it('does NOT retry an agent that merely writes about rate limits and exits clean', () => {
    // The false positive this guard exists for: a doc/diagram agent describing retry
    // policy would otherwise be re-run as if it had been rate-limited.
    const tail = 'Wrote the section on handling 429 rate limit responses and quota backoff.'
    expect(classifyEngineFailure(0, tail)).toBe('permanent')
  })

  it('classifies auth and ordinary agent failures as permanent', () => {
    expect(classifyEngineFailure(1, 'Invalid API key provided')).toBe('permanent')
    expect(classifyEngineFailure(1, 'not logged in — run `claude login`')).toBe('permanent')
    expect(classifyEngineFailure(2, 'SyntaxError: unexpected token')).toBe('permanent')
    expect(classifyEngineFailure(0, '')).toBe('permanent')
  })
})

describe('retryDelayMs', () => {
  it('backs off exponentially across the allowed attempts', () => {
    expect(retryDelayMs(1)).toBe(4000)
    expect(retryDelayMs(2)).toBe(12000)
  })

  it('never returns a negative or zero delay for a non-positive attempt', () => {
    expect(retryDelayMs(0)).toBe(4000)
  })

  it('caps total added latency to well under a minute', () => {
    let total = 0
    for (let i = 1; i <= MAX_TRANSIENT_RETRIES; i++) total += retryDelayMs(i)
    expect(total).toBeLessThan(60000)
  })
})
