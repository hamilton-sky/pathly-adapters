// Shared "add to board" plumbing for editor artifacts (diagram cards, Analyze reports).
// All USER-triggered, renderer-side — the generating agent never posts to the board. Writes
// the artifact to a file and posts it as a comms artifact via the existing commsApi.

import { writeFile } from '../../services/pathlyApi'
import { apiPostArtifact } from '../../store/commsApi'

/** Artifact of `pathly/plans/<feature>/…` → that feature's board; anything else → global. */
export function boardTargetForFile(filePath: string): {
  feature: string
  board: string
  scope: string
} {
  const m = filePath.replace(/\\/g, '/').match(/\/pathly\/plans\/([^/]+)\//)
  if (m) return { feature: m[1], board: 'feature', scope: m[1] }
  return { feature: 'global', board: 'global', scope: 'global' }
}

/**
 * Write `content` to `artifactPath`, then post it to the board (target derived from
 * `sourceFile`'s location). Returns the board message id, or null on failure.
 */
export async function publishArtifactToBoard(
  sourceFile: string,
  artifactPath: string,
  content: string,
  text: string,
  type: string,
): Promise<string | null> {
  try {
    await writeFile(artifactPath, content)
  } catch {
    return null
  }
  const { feature, board, scope } = boardTargetForFile(sourceFile)
  return apiPostArtifact(feature, board, scope, text, artifactPath, type)
}
