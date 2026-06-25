// summaryPrompt — builds the artifact-summary prompt for aiRouter.runJob.
//
// Mirrors the intent of the server-side `_build_topic_map_prompt`
// (src/pathly_orchestrator/runner/inference.py): ask for a compact topic map —
// one line per heading with a short gloss, capped item count, output only the
// lines. Keeping the shape identical means client-computed summaries read the
// same as the legacy server ones. Pure function, no React, no I/O.

/** Same 8k truncation the server applies before prompting. */
const MAX_CHARS = 8000

/**
 * Build the topic-map summary prompt for a Markdown artifact's text.
 * @param text          full file contents
 * @param maxSentences  max number of topic-map lines (default 3, matching the server)
 */
export function buildSummarizePrompt(text: string, maxSentences = 3): string {
  const truncated = text.length > MAX_CHARS ? text.slice(0, MAX_CHARS) : text
  return (
    `List the SUBJECTS this Markdown document covers as a compact topic map — ` +
    `one line per heading with a short gloss (what that section is about, not its details). ` +
    `Maximum ${maxSentences} items. Output ONLY the topic-map lines, no preamble.\n\n` +
    `Document:\n${truncated}`
  )
}
