// summarizeArtifact — client-side summary orchestration for dropped/uploaded and
// re-summarized artifacts (unified-ai-routing Conv 3).
//
// The server summarizer is deliberately disabled for this path (the artifact is
// posted with summary_backend:'minilm', so index_artifact_async produces no prose).
// Instead the CLIENT runs aiRouter against the user's chosen target and writes the
// result back via apiSetArtifactSummary. Off ⇒ no summary (filename/title only).
//
// Pure orchestration (no React) so the drop handler and the per-card Re-summarize
// button share one implementation; kept out of JSX per the UI rules.

import { runJob, isOff, type AiSelection } from '../../../../services/aiRouter'
import { buildSummarizePrompt, parseStructuredSummary } from '../../../../services/summaryPrompt'
import { composeClientSkill } from '../../../../services/skillCompose'
import { readFile, deleteFile } from '../../../../services/pathlyApi'
import { resolveArtifactPath } from '../artifactPath'
import { featureFromPath } from '../../../../utils/featureFromPath'
import { useToastStore } from '../../../../store/toastStore'
import {
  fetchArtifacts,
  apiEditMessage,
  apiSetArtifactSummary,
  SUMMARY_STYLE_DEFAULT,
  type AiSelectionDto,
  type SummaryStyle,
} from '../../../../store/commsApi'

/** Only Markdown/plain-text artifacts are summarized (mirrors the server's .md-only rule). */
export function isSummarizable(atype: string | undefined, name: string): boolean {
  if (atype === 'md') return true
  const ext = name.split('.').pop()?.toLowerCase() ?? ''
  return ext === 'md' || ext === 'markdown' || ext === 'txt'
}

/** Resolve the comms_artifacts row id for a freshly-posted artifact message. */
async function artifactIdForMessage(messageId: string): Promise<string | null> {
  const rows = await fetchArtifacts(messageId)
  return rows[0]?.id ?? null
}

// Summary DEPTH style → which development/summarize* skill the client composes. The format is
// owned by the skill (Pathly), so it is identical no matter which CLI engine runs it. Shared
// with the Re-summarize hook so every summary path honours the same depth (DRY).
export const STYLE_SKILL: Record<SummaryStyle, string> = {
  gist: 'development/summarize-gist',
  'topic-map': 'development/summarize',
  detailed: 'development/summarize-detailed',
}

// The CLI engine writes its summary to a sibling file (the file-based capture contract); poll
// for it after the engine exits. Mirrors the editor's pollForFile cadence.
export async function pollSummaryFile(path: string, tries = 5, delayMs = 600): Promise<string | null> {
  for (let i = 0; i < tries; i++) {
    if (i > 0) await new Promise<void>((r) => setTimeout(r, delayMs))
    const c = await readFile(path)
    if (c != null && c.trim()) return c
  }
  return null
}

// Strip terminal escape codes that leak through the stdout-tail fallback capture (e.g.
// \x1b[>4m, \x1b[<u — private-mode CSI). The clean file/model paths are unaffected.
export function stripAnsi(text: string): string {
  return text
    .replace(/\x1b\[[\x30-\x3f]*[\x20-\x2f]*[\x40-\x7e]/g, '')
    .replace(/\x1b\][\s\S]*?(?:\x07|\x1b\\)/g, '')
    .replace(/\x1b[@-Z\\-_]/g, '')
    .trim()
}

/**
 * The shared core for the AUTO-summary paths (client drop + the server-initiated
 * SUMMARY_REQUEST SSE): read the artifact's text, run the chosen target at the given
 * depth `style`, and write the description + summary back. Best-effort — returns true
 * only on a successful writeback; never throws.
 *
 * Mirrors the Re-summarize path (useResummarize): CLI ENGINE targets compose the depth
 * skill (STYLE_SKILL[style]) and capture the result from a sibling `.summary` FILE —
 * stdout-tail scraping mangled codex/claude output. MODEL targets return clean text
 * from the bare prompt. The two paths share STYLE_SKILL / pollSummaryFile / stripAnsi so
 * the depth + capture behaviour can't fork.
 *
 * The caller filters Off out before calling (runJob throws on the Off sentinel).
 */
export async function summarizeArtifactById(
  messageId: string,
  artifactId: string,
  artifactPath: string,
  selection: AiSelection,
  cwd?: string,
  style: SummaryStyle = SUMMARY_STYLE_DEFAULT,
  note?: string,
): Promise<boolean> {
  if (isOff(selection)) return false
  // Local models are a separate system (chat only). A summary must run on a CLI agent so it goes
  // through the ONE gate (run_id + cost + policy) — the selector no longer offers local models for
  // summaries, and any stale stored local-model target is coerced to the default CLI adapter here.
  if (selection.type === 'model') selection = { type: 'engine', id: 'claude' }
  const name = artifactPath.split(/[/\\]/).pop() ?? artifactPath
  if (!isSummarizable(undefined, name)) return false

  try {
    const abs = resolveArtifactPath(artifactPath, cwd)
    // Attribute the summary run to the artifact's feature board (Pipeline), not '(project)'.
    const feature = featureFromPath(artifactPath)
    const text = await readFile(abs)
    if (!text || !text.trim()) return false

    // The board's per-board default instruction is appended mid-prompt (after the
    // dash-safe composed body) so it can never break argv parsing — mirrors the
    // per-artifact "special request" in useResummarize.
    const noteSuffix = note && note.trim()
      ? `\n\n## Additional request from the user\n${note.trim()}`
      : ''

    // CLI ENGINE: compose the depth skill and have the engine WRITE its summary to a sibling
    // file, then read it — the reliable file-based capture the Re-summarize path uses. Falls
    // back to the bare prompt when /skills/compose is unreachable.
    let raw: string | null = null
    if (selection.type === 'engine') {
      const outAbs = `${abs}.summary`
      const composed = await composeClientSkill(
        STYLE_SKILL[style],
        selection.id,
        { source_path: abs, out_path: outAbs, kind: 'summary' },
        { projectRoot: cwd },
      )
      if (composed) {
        await runJob({ kind: 'summarize', prompt: composed + noteSuffix, cwd, feature }, selection)
        const fileText = await pollSummaryFile(outAbs)
        void deleteFile(outAbs).catch(() => {})
        if (fileText == null) return false
        raw = stripAnsi(fileText)
        if (/^ERROR:/i.test(raw)) {
          throw new Error(raw.replace(/^ERROR:\s*/i, '') || 'the engine reported an error')
        }
      }
    }
    // MODEL target, or engine fallback when compose is unreachable: bare prompt + returned text.
    if (raw == null) {
      const result = await runJob(
        { kind: 'summarize', prompt: buildSummarizePrompt(text, style) + noteSuffix, cwd, feature },
        selection,
      )
      raw = (result.text ?? '').trim()
    }
    if (!raw) return false

    // ONE parser shared with Re-summarize (summaryPrompt.parseStructuredSummary): markdown
    // ## Description / ## Summary. The description refreshes the artifact's message text (the
    // card's Description); the summary always saves.
    const { description, summary } = parseStructuredSummary(raw)
    if (!summary) return false

    if (description) await apiEditMessage(messageId, description)
    return apiSetArtifactSummary(artifactId, summary, selection as AiSelectionDto)
  } catch (err) {
    // Surface the reason instead of failing silently — common causes: a local model that
    // isn't installed (Ollama not running), or the engine not writing the summary file.
    const msg = err instanceof Error ? err.message : String(err)
    useToastStore.getState().push(`Summary failed: ${msg}`, 'error', { category: 'agent_done' })
    return false
  }
}

export interface SummarizeArtifactArgs {
  /** The artifact message id returned by apiPostArtifact. */
  messageId: string
  /** Absolute path of the artifact file (to read its text). */
  path: string
  /** Display type (md/code/…); only md/txt are summarized. */
  atype?: string
  /** The chosen AI target. Off ⇒ skip summarization. */
  selection: AiSelection
  /** Spawn cwd for CLI-engine targets (project root). */
  cwd?: string
  /** Summary depth; defaults to the app default (topic-map) when omitted. */
  style?: SummaryStyle
  /** Per-board default instruction appended to the summary prompt (optional). */
  note?: string
}

/**
 * Run the chosen target over the artifact's text and write the summary back.
 * Best-effort: returns true on a successful writeback, false on skip/failure.
 * Never throws — drop/upload must not be blocked by a summary failure.
 */
export async function summarizeArtifact(args: SummarizeArtifactArgs): Promise<boolean> {
  const { messageId, path, atype, selection, cwd, style, note } = args
  if (isOff(selection)) return false
  const name = path.split(/[/\\]/).pop() ?? path
  if (!isSummarizable(atype, name)) return false

  const artifactId = await artifactIdForMessage(messageId)
  if (!artifactId) return false

  return summarizeArtifactById(messageId, artifactId, path, selection, cwd, style, note)
}

/** Parse a stored summary_selection JSON string into an AiSelection, or null. */
export function parseSelection(raw: string | null | undefined): AiSelection | null {
  if (!raw) return null
  try {
    const p = JSON.parse(raw) as { type?: string; id?: string }
    if ((p.type === 'model' || p.type === 'engine') && typeof p.id === 'string' && p.id) {
      return { type: p.type, id: p.id }
    }
  } catch { /* malformed — fall back */ }
  return null
}

