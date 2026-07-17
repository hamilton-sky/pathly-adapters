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

/** One labeled part of a composed prompt (mirrors compose_skill_segments). */
export interface ComposedSegment {
  id: string
  /** 'body' | 'default' | 'fragment' | 'ability' — the layer this part came from. */
  kind: string
  label: string
  text: string
  source: string
  optional: boolean
  requires: string | null
  included: boolean
}

export interface ComposedSkill {
  prompt: string
  segments: ComposedSegment[]
}

/**
 * Compose a skill's full body WITH layer-3 abilities appended — the real prompt a board run
 * will send, plus its labeled segments. Used by the run gates so the Sections cell-editor
 * operates on the ACTUAL composed prompt (skill + fragments + abilities) and knows each cell's
 * layer; the trimmed result can then be sent verbatim as prompt_override.
 * @returns the composed prompt + segments, or `null` on any failure (caller falls back).
 */
export async function composeSkillPrompt(
  skill: string,
  opts: { adapter?: string; abilityIds?: string[]; projectRoot?: string } = {},
): Promise<ComposedSkill | null> {
  if (!skill) return null
  try {
    const r = await apiFetch('/skills/compose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        skill,
        adapter: opts.adapter ?? 'claude',
        ability_ids: opts.abilityIds ?? [],
        project_root: opts.projectRoot ?? '',
      }),
    })
    if (!r.ok) return null
    const data = (await r.json()) as { prompt?: string; segments?: ComposedSegment[] }
    if (typeof data.prompt !== 'string' || !data.prompt.trim()) return null
    return { prompt: data.prompt, segments: Array.isArray(data.segments) ? data.segments : [] }
  } catch {
    return null
  }
}

/**
 * The prompt's four-layer model, as the Sections editor sees it:
 *   'skill'    — the skill body (the task). Togglable.
 *   'ability'  — layer-3 approach/domain packs the user opted in. Togglable.
 *   'fragment' — Pathly's PLATFORM layer (defaults + fragments): board CRUD, progress
 *                logging, the AGENT_DONE completion report. LOCKED — unchecking
 *                `## Completion report` makes the run write no AGENT_DONE (it vanishes from
 *                RECENT and goes unbilled); unchecking comms-post silently stops board posts.
 */
export type PromptLayer = 'skill' | 'ability' | 'fragment'

/**
 * Map every heading in the composed prompt to the LAYER it came from, so the Sections editor
 * can group/colour cells and lock the platform layer. Covers `# ` and `## ` (the depths the
 * cell splitter uses). Headings not in the map default to 'skill'.
 */
export function headingLayers(segments: ComposedSegment[]): Record<string, PromptLayer> {
  const out: Record<string, PromptLayer> = {}
  for (const s of segments) {
    const layer: PromptLayer =
      s.kind === 'ability' ? 'ability' : s.kind === 'body' ? 'skill' : 'fragment'
    for (const line of s.text.split('\n')) {
      const isH1 = line.startsWith('# ') && !line.startsWith('## ')
      const isH2 = line.startsWith('## ') && !line.startsWith('### ')
      if (!isH1 && !isH2) continue
      out[(isH2 ? line.slice(3) : line.slice(2)).trim()] = layer
    }
  }
  return out
}
