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
 * The `## ` headings that belong to Pathly's PLATFORM layer (defaults + fragments) — the
 * un-editable layer that owns board CRUD, progress logging, and the AGENT_DONE completion
 * report. The Sections cell-editor locks these: unchecking `## Completion report` would make
 * the run write no AGENT_DONE (it vanishes from RECENT and goes unbilled), and unchecking
 * `comms-post` would silently stop it posting to the board.
 */
export function platformHeadings(segments: ComposedSegment[]): string[] {
  const out: string[] = []
  for (const s of segments) {
    if (s.kind !== 'fragment' && s.kind !== 'default') continue
    for (const line of s.text.split('\n')) {
      if (line.startsWith('## ') && !line.startsWith('### ')) out.push(line.slice(3).trim())
    }
  }
  return out
}
