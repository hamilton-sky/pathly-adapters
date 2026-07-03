// Shared "add to board" plumbing for editor artifacts (diagram cards, Analyze reports).
// All USER-triggered, renderer-side — the generating agent never posts to the board. Writes
// the artifact to a file and posts it as a comms artifact via the existing commsApi.

import { writeFile } from '../../services/pathlyApi'
import { apiPostArtifact } from '../../store/commsApi'

/** Artifact of `pathly/features/<feature>/…` (or legacy `pathly/plans/…`) → that feature's
 *  board; anything else → global. */
export function boardTargetForFile(filePath: string): {
  feature: string
  board: string
  scope: string
} {
  const m = filePath.replace(/\\/g, '/').match(/\/pathly\/(?:features|plans)\/([^/]+)\//)
  if (m) return { feature: m[1], board: 'feature', scope: m[1] }
  return { feature: 'global', board: 'global', scope: 'global' }
}

/**
 * Project-level home for board artifact copies — `<root>/pathly/board-artifacts/<fileName>`.
 * Board copies live HERE, not next to the source, so archiving/moving a plan folder doesn't
 * dangle the board card. `fs.write` creates the dir on demand. Returns '' when no root is
 * known so callers can fall back to a next-to-source path.
 */
export function boardArtifactPath(projectRoot: string, fileName: string): string {
  const root = projectRoot.replace(/\\/g, '/').replace(/\/$/, '')
  if (!root) return ''
  return `${root}/pathly/board-artifacts/${fileName}`
}

/**
 * Write `content` to `artifactPath`, then post it to the board. `target` overrides the
 * destination (the user's dropdown pick); when omitted the target is derived from
 * `sourceFile`'s location. Returns the board message id, or null on failure.
 */
export async function publishArtifactToBoard(
  sourceFile: string,
  artifactPath: string,
  content: string,
  text: string,
  type: string,
  target?: { feature: string; board: string; scope: string },
): Promise<string | null> {
  try {
    await writeFile(artifactPath, content)
  } catch {
    return null
  }
  const { feature, board, scope } = target ?? boardTargetForFile(sourceFile)
  return apiPostArtifact(feature, board, scope, text, artifactPath, type)
}
