// summaryFormat — fetch the single-sourced output-format contract for a summary depth.
//
// The contract lives in core/templates/summary/<style>.md and is served by
// GET /skills/summary-format/<style>. BOTH the composed prompt (the server substitutes
// <summary_format> from that file) and the depth-picker preview read the SAME file, so the
// shape the agent fills and the shape the user previews can never drift. Returns '' on any
// failure (server down / unknown style) so the picker simply shows no preview.

import { apiFetch } from '../lib/config'
import type { SummaryStyle } from '../store/commsApi'

const _cache = new Map<SummaryStyle, string>()

/** Fetch the output-format contract for a summary depth. Cached; returns '' on failure. */
export async function fetchSummaryFormat(style: SummaryStyle): Promise<string> {
  const hit = _cache.get(style)
  if (hit != null) return hit
  try {
    const r = await apiFetch(`/skills/summary-format/${style}`)
    if (!r.ok) return ''
    const data = (await r.json()) as { format?: string }
    const fmt = (data.format ?? '').trim()
    if (fmt) _cache.set(style, fmt)
    return fmt
  } catch {
    return ''
  }
}
