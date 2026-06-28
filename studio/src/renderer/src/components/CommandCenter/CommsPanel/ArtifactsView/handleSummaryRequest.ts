// handleSummaryRequest — the client side of the server-initiated summary handoff
// (unified-ai-routing Conv 4).
//
// The server runs NO inference: on an artifact post it emits a `summary_request`
// comms-SSE event carrying the artifact id/path, scope, and the server-resolved AI
// target. This handler runs aiRouter against that target and writes the result back
// via summarizeArtifactById (the same shared core the drop / Re-summarize paths use).
//
// Best-effort: every failure is swallowed with console.debug so a bad summary never
// throws into the SSE message loop. A module-level dedup guard means that when more
// than one board panel is mounted for the same scope, the artifact is summarized
// exactly once.

import { isOff, type AiSelection } from '../../../../services/aiRouter'
import { useProjectStore } from '../../../../store/projectStore'
import { apiGetDefaultStyle } from '../../../../store/commsApi'
import { summarizeArtifactById } from './summarizeArtifact'

/** Shape of the server's summary_request SSE payload (loosely typed at the boundary). */
export interface SummaryRequestEvent {
  artifact_id?: string
  message_id?: string
  artifact_path?: string
  selection?: { type?: string; id?: string }
}

// Artifacts already handled this session — prevents duplicate aiRouter runs when
// several CommsPanel instances (feature / project / global views) subscribe to the
// same scope and each receive the broadcast.
const handled = new Set<string>()

/** Narrow the loosely-typed event selection into a valid AiSelection, or null. */
function asSelection(sel: SummaryRequestEvent['selection']): AiSelection | null {
  if (
    sel != null &&
    (sel.type === 'model' || sel.type === 'engine') &&
    typeof sel.id === 'string' &&
    sel.id
  ) {
    return { type: sel.type, id: sel.id }
  }
  return null
}

/**
 * React to a `summary_request` comms-SSE event: run the resolved target over the
 * artifact's text and POST the summary back. Never throws.
 */
export async function handleSummaryRequest(data: SummaryRequestEvent): Promise<void> {
  const artifactId = data.artifact_id
  const messageId = data.message_id
  const artifactPath = data.artifact_path
  const selection = asSelection(data.selection)
  if (!artifactId || !messageId || !artifactPath || !selection) return
  if (isOff(selection)) return
  if (handled.has(artifactId)) return
  handled.add(artifactId)

  try {
    const cwd = useProjectStore.getState().projectPath.replace(/\\/g, '/').replace(/\/$/, '') || undefined
    // Honour the app-default depth (same setting the drop toolbar persists); null ⇒ topic-map.
    const style = (await apiGetDefaultStyle()) ?? undefined
    await summarizeArtifactById(messageId, artifactId, artifactPath, selection, cwd, style)
  } catch (err) {
    // Best-effort: a summary failure must not break the SSE loop. Release the
    // dedup guard so a later summary_request (or manual retry) can re-run instead
    // of the artifact being permanently marked handled for the session.
    handled.delete(artifactId)
    console.debug('handleSummaryRequest failed', err)
  }
}
