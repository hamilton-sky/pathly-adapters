// HQ operator (pathly/features/local-operator): the local model may PROPOSE
// actions, never run them. llm:chat offers the turn's tools (from POST
// /hq/prompt — only the actions the user enabled and Settings allows) as
// node-llama-cpp session functions whose handlers only RECORD the call and tell
// the model it has not run. The proposals go back to the renderer, which turns
// them into confirm cards; execution happens on the user's Run click, outside
// the model turn. Pure (no Electron, no node-llama-cpp) so it can be unit-tested.

/** One function the model may call — the server's tool spec. */
export interface HqToolSpec {
  name: string
  description: string
  parameters: Record<string, unknown>
}

/** A recorded call: becomes one confirm card. */
export interface ToolProposal {
  name: string
  args: Record<string, unknown>
}

/** The most cards one reply can carry (the server enforces the same cap). */
export const MAX_PROPOSALS = 8

// Worded so the answer speaks to the user ("you") — measured with Qwen3 8B: a
// third-person reply ("the user sees a card") got echoed back in the third person.
export const PROPOSED_REPLY =
  'Proposed, NOT run. Tell the user, speaking to them as "you", that it is waiting on the card below for their Run click. Never say it is done.'
export const CAP_REPLY = `Not proposed: ${MAX_PROPOSALS} actions is the limit for one reply.`
export const UNKNOWN_REPLY = 'Not proposed: that action is not offered.'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export interface ProposalRecorder {
  readonly proposals: ToolProposal[]
  /** Record a call; returns what the model is told. */
  record: (name: string, args: unknown) => string
}

export function createProposalRecorder(tools: HqToolSpec[], max = MAX_PROPOSALS): ProposalRecorder {
  const offered = new Set(tools.map((t) => t.name))
  const proposals: ToolProposal[] = []
  return {
    proposals,
    record(name, args) {
      // Belt and braces: the grammar only lets the model name offered tools.
      if (!offered.has(name)) return UNKNOWN_REPLY
      if (proposals.length >= max) return CAP_REPLY
      proposals.push({ name, args: isRecord(args) ? { ...args } : {} })
      return PROPOSED_REPLY
    },
  }
}

/** node-llama-cpp session functions for *tools*: each handler only records. */
export function recordingFunctions(
  tools: HqToolSpec[],
  recorder: ProposalRecorder,
): Record<string, { description: string; params: Record<string, unknown>; handler: (params: unknown) => string }> {
  return Object.fromEntries(
    tools.map((t) => [
      t.name,
      { description: t.description, params: t.parameters, handler: (params: unknown) => recorder.record(t.name, params) },
    ]),
  )
}
