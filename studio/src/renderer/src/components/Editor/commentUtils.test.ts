import { describe, it, expect } from 'vitest'
import { describeAgentFailure } from './commentUtils'

// Mirror-guard for main/ipc/engineFailure.ts: any failure the spawn gate treats as transient
// must read as an upstream fault here, never as "the agent wrote nothing".
describe('describeAgentFailure', () => {
  it('names a capacity refusal as upstream, not as a missing file', () => {
    const msg = describeAgentFailure(
      'Diagram',
      'simulator.md',
      1,
      '{"type":"turn.failed","error":{"message":"Selected model is at capacity. Please try a different model."}}',
    )
    expect(msg).toMatch(/at capacity/)
    expect(msg).not.toMatch(/wrote nothing|no file written/)
  })

  it('still separates rate limit / quota from capacity', () => {
    expect(describeAgentFailure('Split', 'a.md', 1, 'Error: 429 too many requests')).toMatch(/rate limit \/ quota/)
  })

  it('still separates auth failures', () => {
    expect(describeAgentFailure('Analyze', 'a.md', 1, 'invalid api key')).toMatch(/auth \/ login/)
  })

  it('falls back to the engine exit code, then to "wrote nothing"', () => {
    expect(describeAgentFailure('Send', 'a.md', 3, '')).toMatch(/engine exited \(code 3\)/)
    expect(describeAgentFailure('Send', 'a.md', 0, '')).toMatch(/engine wrote nothing/)
  })
})
