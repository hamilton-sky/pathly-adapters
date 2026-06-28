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
import { readFile } from '../../../../services/pathlyApi'
import { resolveArtifactPath } from '../artifactPath'
import { useToastStore } from '../../../../store/toastStore'
import {
  fetchArtifacts,
  apiEditMessage,
  apiSetArtifactSummary,
  type AiSelectionDto,
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

/**
 * The shared core: read the artifact's text, run the chosen target over it, and
 * write the summary back to comms_artifacts. Every summary path (client drop,
 * Re-summarize, the server-initiated SUMMARY_REQUEST SSE) funnels through here so
 * there is ONE implementation (DRY). Best-effort — returns true only on a
 * successful writeback; never throws.
 *
 * The caller is responsible for resolving the selection (Off must be filtered out
 * before calling — runJob throws on the Off sentinel).
 */
export async function summarizeArtifactById(
  messageId: string,
  artifactId: string,
  artifactPath: string,
  selection: AiSelection,
  cwd?: string,
): Promise<boolean> {
  if (isOff(selection)) return false
  const name = artifactPath.split(/[/\\]/).pop() ?? artifactPath
  if (!isSummarizable(undefined, name)) return false

  try {
    const text = await readFile(resolveArtifactPath(artifactPath, cwd))
    if (!text || !text.trim()) return false

    const result = await runJob(
      { kind: 'summarize', prompt: buildSummarizePrompt(text), cwd },
      selection,
    )
    // ONE parser shared with the Re-summarize path (summaryPrompt.parseStructuredSummary):
    // markdown ## Description / ## Summary. The description is optional — when present it
    // refreshes the artifact's message text (the card's Description); the summary always saves.
    const { description, summary } = parseStructuredSummary(result.text ?? '')
    if (!summary) return false

    if (description) await apiEditMessage(messageId, description)
    return apiSetArtifactSummary(artifactId, summary, selection as AiSelectionDto)
  } catch (err) {
    // Surface the reason instead of failing silently — the most common cause is a
    // model target that isn't installed locally (Ollama not running / not pulled).
    // The engine default avoids this, but a user-picked model can still hit it.
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
}

/**
 * Run the chosen target over the artifact's text and write the summary back.
 * Best-effort: returns true on a successful writeback, false on skip/failure.
 * Never throws — drop/upload must not be blocked by a summary failure.
 */
export async function summarizeArtifact(args: SummarizeArtifactArgs): Promise<boolean> {
  const { messageId, path, atype, selection, cwd } = args
  if (isOff(selection)) return false
  const name = path.split(/[/\\]/).pop() ?? path
  if (!isSummarizable(atype, name)) return false

  const artifactId = await artifactIdForMessage(messageId)
  if (!artifactId) return false

  return summarizeArtifactById(messageId, artifactId, path, selection, cwd)
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

