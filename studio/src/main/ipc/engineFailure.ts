// Transient-failure classification for CLI-engine spawns.
//
// A CLI engine can die for two very different reasons, and the gate must tell them apart:
//   • TRANSIENT — the provider refused the turn (rate limit, quota burst, "at capacity",
//     overloaded, 5xx). Nothing is wrong with the prompt; the same run would succeed later.
//   • PERMANENT — bad auth, a broken prompt, a real agent error. Retrying just burns quota.
//
// Only transient failures are worth retrying and worth arming the gate's cooldown, so this
// module owns the single definition both decisions read (terminal.ts).
//
// MIRROR: the renderer has its own user-facing classifier for toast copy in
// components/Editor/commentUtils.ts::describeAgentFailure. It must stay in sync with the
// patterns here. They cannot share a module — tsconfig.node.json scopes the main bundle to
// src/main/**, so a renderer import would not typecheck.

/** Provider-side "come back later" signals. Not an agent error — the turn never ran. */
const TRANSIENT_RE =
  /rate.?limit|usage limit|quota|\b429\b|too many requests|overloaded|at capacity|capacity|\b50[023]\b|service unavailable|temporarily unavailable|try again later|server_error|api_error/i

/**
 * Engine-level abort markers that are trustworthy even when the process exits 0.
 * Some CLIs report a failed turn in their JSON event stream and still exit clean
 * (codex `exec --json` emits `{"type":"turn.failed", ...}`), so exit code alone
 * would miss the failure entirely.
 */
const ENGINE_ABORT_RE = /"type"\s*:\s*"turn\.failed"|"type"\s*:\s*"error"|"is_error"\s*:\s*true/i

export type FailureClass = 'transient' | 'permanent'

/**
 * Classify a finished engine run.
 *
 * `transient` requires BOTH a transient phrase AND real evidence the run failed — a
 * non-zero exit, or an engine abort marker. Without that second condition an agent that
 * merely *writes about* rate limits in its output (entirely possible — a doc agent
 * describing retry policy) would be misread as rate-limited and retried.
 */
export function classifyEngineFailure(exitCode: number, tail: string): FailureClass {
  if (!TRANSIENT_RE.test(tail)) return 'permanent'
  const failed = exitCode !== 0 || ENGINE_ABORT_RE.test(tail)
  return failed ? 'transient' : 'permanent'
}

/** How many times a transient failure is re-run before the gate gives up and reports it. */
export const MAX_TRANSIENT_RETRIES = 2

/** Exponential backoff between transient retries: 4s, then 12s. */
export function retryDelayMs(attempt: number): number {
  return 4000 * Math.pow(3, Math.max(0, attempt - 1))
}
