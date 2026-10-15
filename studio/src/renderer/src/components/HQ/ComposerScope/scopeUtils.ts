import type { HqContextManifest } from '../../../store/chatStore'
import { HQ_SECTIONS, type HqSectionName } from '../../../store/hqContextStore'

/** Before any answer there is no manifest to read the budget from — this is the
 *  server's default (hq_context.DEFAULT_BUDGET_TOKENS / hq.context_budget_tokens). */
export const DEFAULT_HQ_BUDGET_TOKENS = 6000

/** Sections ticked, of all sections ("5/6" on the Context chip). */
export function contextCount(enabled: Record<HqSectionName, boolean>): { on: number; total: number } {
  return { on: HQ_SECTIONS.filter((s) => enabled[s.name]).length, total: HQ_SECTIONS.length }
}

/** A section's size from the latest answer's manifest, or null when that
 *  answer never read it (off, empty, no project root, or an older server). */
export function sectionTokens(manifest: HqContextManifest | null, name: string): number | null {
  const tokens = manifest?.sections.find((s) => s.name === name)?.tokens
  return tokens && tokens > 0 ? tokens : null
}

export interface ContextEstimate {
  /** Tokens the ticked sections took on the latest answer. */
  tokens: number
  /** Ticked sections with no measured size: their cost is unknown until asked once. */
  unmeasured: number
  budget: number
}

/** Estimate the next question's packet from the latest answer's per-section
 *  sizes. Board content changes between questions, so this is a guide, not a
 *  promise; the server still cuts lowest-priority sections to fit the budget. */
export function estimateContext(
  enabled: Record<HqSectionName, boolean>,
  manifest: HqContextManifest | null,
): ContextEstimate {
  let tokens = 0
  let unmeasured = 0
  for (const s of HQ_SECTIONS) {
    if (!enabled[s.name]) continue
    const size = sectionTokens(manifest, s.name)
    if (size === null) unmeasured += 1
    else tokens += size
  }
  return { tokens, unmeasured, budget: manifest?.budget || DEFAULT_HQ_BUDGET_TOKENS }
}
