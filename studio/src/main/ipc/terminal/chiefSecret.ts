// The chief's hook secret — claimed once from the server, for the chief claude's environment only.
//
// The server keeps a claude chief's hook secret in memory and hands it out once, to a tokenless
// caller, at POST /chief/hook-secret; a second claim closes the chief. Studio's main process is
// that one claimer: for an interactive claude tab whose run id is a chief run id it claims the
// secret right before the spawn and passes it to buildSpawnEnv, which puts it in that child's
// environment only. The value is never written to this process's `process.env`, never logged
// and never sent to the renderer. A claim that fails (409, any other status, a network error)
// refuses the spawn: the server's watcher then closes the session as never started.

import { getApiBase, getApiSecret } from '../../apiConfig'

const CHIEF_RUN_RE = /^chief-[0-9a-f]{12}$/

/** Is this the spawn of a claude chief: an interactive tab, chief run id, argv `claude …`? */
export function isChiefClaudeSpawn(runId: string | undefined, argv: string[] | undefined, interactive: boolean): boolean {
  return interactive && !!runId && CHIEF_RUN_RE.test(runId) && argv?.[0] === 'claude'
}

/** Claim the chief's hook secret: the secret on a 200, else null (any other status, a failure). */
export async function claimChiefHookSecret(runId: string): Promise<string | null> {
  try {
    const res = await fetch(`${getApiBase()}/chief/hook-secret`, {
      method: 'POST',
      // No X-Pathly-Run-Token: the route refuses any caller that sends one.
      headers: { 'Content-Type': 'application/json', 'X-Pathly-Secret': getApiSecret() },
      body: JSON.stringify({ run_id: runId }),
    })
    if (res.status !== 200) return null
    const body = (await res.json()) as { hook_secret?: unknown } | null
    const secret = body?.hook_secret
    return typeof secret === 'string' && secret ? secret : null
  } catch {
    return null
  }
}

/** The secret a spawn's environment gets: undefined when it is not a claude chief; a claude
 *  chief whose claim fails is refused (throws). */
export async function chiefSecretForSpawn(runId: string | undefined, argv: string[] | undefined, interactive: boolean): Promise<string | undefined> {
  if (!runId || !isChiefClaudeSpawn(runId, argv, interactive)) return undefined
  const secret = await claimChiefHookSecret(runId)
  if (!secret) {
    throw new Error('The chief could not get its hook secret from the server, so it was not started. Open the chief again.')
  }
  return secret
}
