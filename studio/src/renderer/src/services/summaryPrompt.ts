// summaryPrompt — builds the artifact-summary prompt for aiRouter.runJob.
//
// This is the FALLBACK prompt builder, used when the fragment-composition seam
// (/skills/compose) is unreachable and for MODEL targets (which return clean text
// directly). It mirrors the three depth skills in core/skills/development:
//   gist       → summarize-gist.md    (one-sentence gist; precision)
//   topic-map  → summarize.md         (compact topic map; balanced)
//   detailed   → summarize-detailed.md(section + key points; recall)
// Keeping the shapes aligned means a fallback summary reads like a composed one.
// Pure function, no React, no I/O.

import type { SummaryStyle } from '../store/commsApi'

/** Same 8k truncation the server applies before prompting. */
const MAX_CHARS = 8000

// One instruction line per DEPTH. The document body is appended after each.
// These intentionally track the wording of the development/summarize* skills so the
// fallback and composed paths produce comparable output.
const STYLE_INSTRUCTION: Record<SummaryStyle, string> = {
  gist:
    `Produce a ONE-SENTENCE gist of this Markdown document: its single most important ` +
    `point — what it is and why it matters. No section breakdown, no list, no preamble — ` +
    `just that one sentence.`,
  'topic-map':
    `List the SUBJECTS this Markdown document covers as a compact topic map — ` +
    `one line per heading with a short gloss (what that section is about, not its details). ` +
    `Maximum 3 items. Output ONLY the topic-map lines, no preamble.`,
  detailed:
    `Produce a DETAILED summary of this Markdown document: for each major section, write a ` +
    `line with the section's topic AND its key points or decisions — not just the heading. ` +
    `Capture specifics (names, APIs, identifiers, decisions, sequence). Output only the ` +
    `section lines, no preamble.`,
}

/**
 * Build the summary prompt for a Markdown artifact's text at the requested DEPTH.
 * @param text   full file contents
 * @param style  summary depth (default 'topic-map', matching the server default)
 */
export function buildSummarizePrompt(text: string, style: SummaryStyle = 'topic-map'): string {
  const truncated = text.length > MAX_CHARS ? text.slice(0, MAX_CHARS) : text
  const instruction = STYLE_INSTRUCTION[style] ?? STYLE_INSTRUCTION['topic-map']
  return `${instruction}\n\nDocument:\n${truncated}`
}
