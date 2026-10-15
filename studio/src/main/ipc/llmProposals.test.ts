import { describe, expect, it } from 'vitest'
import {
  CAP_REPLY,
  createProposalRecorder,
  MAX_PROPOSALS,
  PROPOSED_REPLY,
  recordingFunctions,
  UNKNOWN_REPLY,
  type HqToolSpec,
} from './llmProposals'

const TOOLS: HqToolSpec[] = [
  { name: 'pause_run', description: 'Propose pausing', parameters: { type: 'object', properties: { run_id: { type: 'string' } } } },
  { name: 'post_note', description: 'Propose a note', parameters: { type: 'object', properties: { text: { type: 'string' } } } },
]

/** A stubbed model: calls the session functions it was given, in order. */
function stubModel(functions: ReturnType<typeof recordingFunctions>, calls: [string, unknown][]): string[] {
  return calls.map(([name, params]) => {
    const fn = functions[name]
    return fn ? fn.handler(params) : UNKNOWN_REPLY
  })
}

describe('the operator proposal recorder', () => {
  it('records a call as a proposal and tells the model it has not run', () => {
    const rec = createProposalRecorder(TOOLS)
    const replies = stubModel(recordingFunctions(TOOLS, rec), [['pause_run', { run_id: 'r1' }]])
    expect(replies).toEqual([PROPOSED_REPLY])
    expect(rec.proposals).toEqual([{ name: 'pause_run', args: { run_id: 'r1' } }])
  })

  it('offers the model exactly the given tools, with their schemas', () => {
    const fns = recordingFunctions(TOOLS, createProposalRecorder(TOOLS))
    expect(Object.keys(fns)).toEqual(['pause_run', 'post_note'])
    expect(fns.pause_run.params).toBe(TOOLS[0].parameters)
  })

  it('two calls in one reply are two proposals, in order', () => {
    const rec = createProposalRecorder(TOOLS)
    stubModel(recordingFunctions(TOOLS, rec), [['post_note', { text: 'a' }], ['pause_run', { run_id: 'r2' }]])
    expect(rec.proposals.map((p) => p.name)).toEqual(['post_note', 'pause_run'])
  })

  it('rejects an unknown tool and never records it', () => {
    const rec = createProposalRecorder(TOOLS)
    expect(rec.record('answer_question', { answer: 'yes' })).toBe(UNKNOWN_REPLY)
    expect(rec.proposals).toEqual([])
  })

  it('the 9th call never becomes a proposal (cap at 8)', () => {
    const rec = createProposalRecorder(TOOLS)
    const calls: [string, unknown][] = Array.from({ length: MAX_PROPOSALS + 1 }, (_, i) => ['pause_run', { run_id: `r${i}` }])
    const replies = stubModel(recordingFunctions(TOOLS, rec), calls)
    expect(rec.proposals).toHaveLength(MAX_PROPOSALS)
    expect(replies[MAX_PROPOSALS]).toBe(CAP_REPLY)
  })

  it('never executes anything — a handler only returns text', () => {
    const rec = createProposalRecorder(TOOLS)
    const out = recordingFunctions(TOOLS, rec).pause_run.handler('not an object')
    expect(typeof out).toBe('string')
    expect(rec.proposals[0].args).toEqual({})
  })
})
