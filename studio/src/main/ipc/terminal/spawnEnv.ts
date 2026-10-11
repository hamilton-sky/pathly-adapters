// Env entries Pathly adds to a spawned CLI process. Pure: the caller layers these over
// process.env, so the run token is only ever put in the child's env, never in the main
// process's own, and is never logged.

export interface RunnerMeta {
  run_token?: string
  [key: string]: unknown
}

export function buildSpawnEnv(cwd: string, meta: RunnerMeta | undefined): Record<string, string> {
  // PATHLY_PROJECT_ROOT lets the stop hook (a child of the agent PTY) find the active feature in
  // the DB and write the BILLING_UPDATE; cwd IS the project root (validated by the caller).
  // Runner spawns are billed by the gate -> /runner/terminal/result, so PATHLY_GATE_BILLED makes
  // the claude stop hook skip them instead of double-billing via its "most recent feature" guess.
  return {
    PATHLY_PROJECT_ROOT: cwd,
    // Runner spawns are billed by the gate; the marker makes the interactive stop hook skip them.
    ...(meta ? { PATHLY_GATE_BILLED: '1' } : {}),
    ...(meta?.run_token ? { PATHLY_RUN_TOKEN: meta.run_token } : {}),
  }
}
