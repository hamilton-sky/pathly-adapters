import type { HqContextSection } from '../../../store/chatStore'

/** 1234 -> "1.2k", 999 -> "999": compact token counts for the manifest line. */
export function formatTokens(n: number): string {
  if (!Number.isFinite(n) || n < 0) return '0'
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return `${Math.round(n)}`
}

/** Share of the budget used, clamped to 0–100 (a 0 budget reads as 0%). */
export function usagePercent(tokens: number, budget: number): number {
  if (!Number.isFinite(tokens) || !Number.isFinite(budget) || budget <= 0) return 0
  return Math.min(100, Math.max(0, Math.round((tokens / budget) * 100)))
}

/** Human label for a section row: "included" or "cut - <reason>". */
export function sectionStatusLabel(section: HqContextSection): string {
  if (section.included) return 'included'
  if (section.cut_reason === 'off') return 'off'
  return section.cut_reason ? `cut - ${section.cut_reason}` : 'cut'
}

/** The marker the server puts in the HQ prompt when the board packet cannot be assembled (hq_prompt.UNAVAILABLE_MARKER). A model that echoes it has it stripped from the answer and shown as the amber note instead. */
export const BOARD_CONTEXT_UNAVAILABLE_MARKER = '[board context unavailable]'

export function stripUnavailableMarker(content: string): string {
  return content.split(BOARD_CONTEXT_UNAVAILABLE_MARKER).join('').trim()
}
