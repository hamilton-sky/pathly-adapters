// Abilities = capabilities the composed prompt grants, each backed by a fragment.
// Derived client-side from the fragment set; swap for a real capability index if the
// engine ever exposes one.
export interface Ability {
  id: string
  name: string
  fragment: string
  desc: string
}

export const ABILITIES: Ability[] = [
  { id: 'ab-graph',    name: 'Codebase graph query', fragment: 'code-query',          desc: 'Query the codebase graph + LSP for impact, callers and surrounding context before editing.' },
  { id: 'ab-scout',    name: 'Scout spawning',       fragment: 'scout-choreography',  desc: 'Spawn parallel scout sub-agents to gather multi-file context ahead of acting.' },
  { id: 'ab-board',    name: 'Board posting',        fragment: 'comms-post',          desc: 'Post decisions, discoveries and questions to the shared comms board.' },
  { id: 'ab-catalog',  name: 'Artifact catalog',     fragment: 'catalog-pull',        desc: 'Pull the board catalog of available artifacts to reuse prior work.' },
  { id: 'ab-feedback', name: 'Feedback resolution',  fragment: 'feedback-protocol',   desc: 'Read and resolve open REVIEW / TEST feedback files before completing.' },
  { id: 'ab-report',   name: 'Completion reporting', fragment: 'completion-report',   desc: 'Write the authoritative AGENT_DONE completion report + telemetry.' },
  { id: 'ab-delegate', name: 'Sub-agent delegation', fragment: 'spawn-rules',         desc: 'Governs how and when sub-agents may be spawned and delegated to.' },
  { id: 'ab-context',  name: 'Board context load',   fragment: 'board-start-context', desc: 'Load the starting board context into the prompt at run start.' },
  { id: 'ab-consult',  name: 'Mid-flow consultation',fragment: 'consult',             desc: 'Consult another role mid-flow via a scoped meet / consultation.' },
]
