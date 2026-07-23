// Curated per-fragment purpose + token cost. The /skills/catalog endpoint returns empty
// descriptions and no per-fragment token counts, so this reference map (a fixed, known
// fragment set) gives the UI something meaningful to show. Replace the token figures with
// real measured counts once the composer exposes them. Unknown names fall back to gracefully.
export interface FragmentMeta {
  purpose: string
  tokens: number
}

export const FRAGMENT_META: Record<string, FragmentMeta> = {
  'artifact-register':   { purpose: 'Register produced artifacts on the board (ARTIFACTS.jsonl).', tokens: 41 },
  'artifact-transform':  { purpose: 'Transform an artifact (split / convert) into a new output file.', tokens: 47 },
  'board-init':          { purpose: 'Initialize the board scope + governance context at run start.', tokens: 52 },
  'board-start-context': { purpose: 'Pull the starting board context into the prompt.', tokens: 29 },
  'build-discipline':    { purpose: 'Enforce scope discipline — no unrelated refactors or cleanup.', tokens: 58 },
  'catalog-pull':        { purpose: 'Pull the board catalog of available artifacts for context.', tokens: 33 },
  'client-file-output':  { purpose: 'Write the result to a client-specified output file.', tokens: 30 },
  'code-query':          { purpose: 'Query the codebase graph + LSP (impact / callers / context).', tokens: 48 },
  'comms-post':          { purpose: 'Post decisions, discoveries, and questions to the comms board.', tokens: 38 },
  'completion-report':   { purpose: 'Write the authoritative AGENT_DONE completion report + telemetry.', tokens: 62 },
  'consult':             { purpose: 'Consult another role mid-flow (meet / consultation).', tokens: 36 },
  'feedback-protocol':   { purpose: 'Read and resolve open feedback files (REVIEW / TEST failures).', tokens: 55 },
  'progress-logging':    { purpose: 'Log mid-run progress to the board (PHASE_SUMMARY).', tokens: 34 },
  'scout-choreography':  { purpose: 'Spawn scouts to gather multi-file context before acting.', tokens: 40 },
  'spawn-rules':         { purpose: 'Rules governing sub-agent spawning and delegation.', tokens: 44 },
  'task-dag-post':       { purpose: 'Post the task-DAG (work-list) to the board as goal tasks.', tokens: 45 },
}

export function fragmentPurpose(name: string): string {
  return FRAGMENT_META[name]?.purpose ?? ''
}

export function fragmentTokens(name: string): number {
  return FRAGMENT_META[name]?.tokens ?? 0
}
