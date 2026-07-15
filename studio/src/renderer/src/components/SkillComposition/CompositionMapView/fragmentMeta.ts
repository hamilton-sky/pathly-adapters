// Curated one-line purpose for each known Pathly fragment. The /skills/catalog endpoint
// returns empty `description` fields, so this reference map (a fixed, known fragment set)
// gives the Config view something meaningful to show. Unknown names fall back to ''.
const FRAGMENT_PURPOSE: Record<string, string> = {
  'artifact-register': 'Register produced artifacts on the board (ARTIFACTS.jsonl).',
  'artifact-transform': 'Transform an artifact (split / convert) into a new output file.',
  'board-init': 'Initialize the board scope + governance context at run start.',
  'board-start-context': 'Pull the starting board context into the prompt.',
  'catalog-pull': 'Pull the board catalog of available artifacts for context.',
  'client-file-output': 'Write the result to a client-specified output file.',
  'code-query': 'Query the codebase graph + LSP (impact / callers / context).',
  'comms-post': 'Post decisions, discoveries, and questions to the comms board.',
  'completion-report': 'Write the authoritative AGENT_DONE completion report + telemetry.',
  consult: 'Consult another role mid-flow (meet / consultation).',
  'feedback-protocol': 'Read and resolve open feedback files (REVIEW / TEST failures).',
  'progress-logging': 'Log mid-run progress to the board (PHASE_SUMMARY).',
  'scout-choreography': 'Spawn scouts to gather multi-file context before acting.',
  'spawn-rules': 'Rules governing sub-agent spawning and delegation.',
  'task-dag-post': 'Post the task-DAG (work-list) to the board as goal tasks.',
}

/** One-line purpose for a fragment, or '' when unknown. */
export function fragmentPurpose(name: string): string {
  return FRAGMENT_PURPOSE[name] ?? ''
}
