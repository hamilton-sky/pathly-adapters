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
  // Two sections — Description (1-2 sentence context → the artifact's message text) + Summary
  // (the depth body). Mirrors the composed development/summarize* contract so the host parses
  // both paths identically.
  return (
    `Output these two sections and nothing else.\n\n` +
    `## Description\n1-2 sentences of context: what this document is and why it matters.\n\n` +
    `## Summary\n${instruction}\n\n` +
    `Document:\n${truncated}`
  )
}

/**
 * Fallback 1–2 sentence description derived from the summary text, used when the model
 * didn't emit an explicit `## Description` section. Collapses whitespace, keeps the first
 * one or two sentences, and caps the length so the card's Description stays a short context
 * line rather than a copy of the whole summary.
 */
function deriveDescription(summary: string): string | null {
  const flat = summary.replace(/\s+/g, ' ').trim()
  if (!flat) return null
  const sentences = flat.match(/[^.!?]+[.!?]+/g)
  let out = (sentences ? sentences.slice(0, 2).map((s) => s.trim()).join(' ') : flat).trim()
  if (out.length > 300) out = `${out.slice(0, 299).trimEnd()}…`
  return out || null
}

/**
 * Split a summarize result into its `## Description` and `## Summary` sections. The ONE parser
 * for every summary path (Re-summarize, drop/upload, server-initiated SUMMARY_REQUEST) so the
 * contract can't fork. When the structure is absent (a model/offline path that didn't follow it,
 * or legacy output) the whole thing is the summary and a short description is DERIVED from its
 * first sentences — so a successful summary always refreshes the description instead of leaving
 * the agent's stub title. `description` is null only when there is no summary text at all.
 */
export function parseStructuredSummary(raw: string): { description: string | null; summary: string } {
  const m = raw.match(/#{2,4}\s+Description\s*\n([\s\S]*?)\n#{2,4}\s+Summary\s*\n([\s\S]*)$/i)
  if (m && m[2].trim()) {
    const summary = m[2].trim()
    // Explicit Description wins; if the model left it empty, derive one from the summary.
    return { description: m[1].trim() || deriveDescription(summary), summary }
  }
  const summary = raw.trim()
  return { description: deriveDescription(summary), summary }
}
