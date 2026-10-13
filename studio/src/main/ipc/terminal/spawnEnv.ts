// The environment a spawned PTY child runs with — one concern, kept out of terminal.ts.
//
// Every child gets the project root and an enriched PATH. A runner tab (registered before
// spawn) additionally gets PATHLY_GATE_BILLED, so the interactive stop hook skips it, and —
// when the server minted one — PATHLY_RUN_TOKEN, the per-run identity token. The token is
// passed through exactly as received, only into the child's env: it is never written to
// this process's own `process.env` and never logged.

import { enrichedPath } from './shells'

/** The slice of a registered runner tab this module reads. */
export interface SpawnEnvMeta { run_token?: string }

export function buildSpawnEnv(cwd: string, meta: SpawnEnvMeta | undefined): Record<string, string> {
  // Export PATHLY_PROJECT_ROOT so the stop hook (which runs as a child of this agent PTY) can
  // find the active feature in the DB and write the BILLING_UPDATE. Without it,
  // stop_telemetry.py hits `if not project_root: sys.exit(0)` and in-app COST silently stays
  // blank. cwd IS the project root (validated by the caller); the hook forward-slash-normalizes
  // it, matching the stored fsm_events key.
  // Runner spawns are billed authoritatively by the gate → /runner/terminal/result
  // (adapter-agnostic, run-keyed). Mark them so the claude stop hook SKIPS them and can't
  // double-bill / mis-attribute via its "most recent feature" guess. Interactive claude
  // (no runner tab) carries no marker, so the hook still bills it (its only cost source).
  const env = {
    ...process.env,
    // Widened PATH — a Finder-launched Electron app inherits launchd's minimal PATH, not the
    // user's shell PATH, so without this an engine (or a tool the engine shells out to) can be
    // unresolvable even though it works in the user's terminal.
    PATH: enrichedPath(),
    PATHLY_PROJECT_ROOT: cwd,
    ...(meta ? { PATHLY_GATE_BILLED: '1' } : {}),
  } as Record<string, string>
  // A token inherited from Studio's own environment is never passed on to a child.
  delete env.PATHLY_RUN_TOKEN
  if (meta?.run_token) env.PATHLY_RUN_TOKEN = meta.run_token
  return env
}
