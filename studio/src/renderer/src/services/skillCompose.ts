// skillCompose — the client seam to Pathly's fragment composition.
//
// Client-side actions (artifact Summary, editor Analyze/Split) used to send BARE,
// hand-built prompts to the CLI. This asks the FSM server to compose the SAME
// fragment-stitched prompt that server/FSM actions get (via POST /skills/compose,
// sibling of /skills/preview), so every action connects to Pathly the same way.
//
// Returns null on ANY failure so the caller falls back to its bare prompt builder —
// composition is an enhancement layer, never a hard dependency.

import { apiFetch } from '../lib/config'

export interface ComposeTransform {
  /** Absolute path of the artifact to read. */
  source_path: string
  /** Absolute path the agent must write its derived result to (the host polls this). */
  out_path: string
  /** Transform kind, rendered into the prompt (e.g. "summary", "analysis", "split"). */
  kind: 'summary' | 'analysis' | 'split'
}

interface ComposeOpts {
  projectRoot?: string
  feature?: string
}

/**
 * Compose `skill` into a complete, dash-safe prompt with the transform vars injected.
 * @returns the composed prompt, or `null` if the server is unreachable / errors.
 */
export async function composeClientSkill(
  skill: string,
  adapter: string,
  transform: ComposeTransform,
  opts: ComposeOpts = {},
): Promise<string | null> {
  try {
    const r = await apiFetch('/skills/compose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        skill,
        adapter,
        transform,
        project_root: opts.projectRoot ?? '',
        feature: opts.feature ?? '',
      }),
    })
    if (!r.ok) return null
    const data = (await r.json()) as { prompt?: string; composed?: boolean }
    return typeof data.prompt === 'string' && data.prompt.trim() ? data.prompt : null
  } catch {
    return null
  }
}
