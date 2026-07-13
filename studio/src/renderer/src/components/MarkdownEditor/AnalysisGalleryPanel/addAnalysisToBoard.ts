// "Add to board" for a single analysis report — USER-triggered, renderer-side (the generating
// agent never posts). Freezes the report's markdown to a sibling file and posts it as a comms
// artifact. The card stays — this is a copy, not a move. Mirrors addDiagramToBoard.

import { publishArtifactToBoard, boardArtifactPath } from '../boardArtifacts'
import type { AnalysisEntry } from '../analysisTypes'
import type { BoardTarget } from '../../shared/AddToBoardButton/AddToBoardButton'

/** Returns the new board message id, or null on failure. `target` is the user's board pick;
 *  `projectRoot` routes the copy into the project-level board-artifacts dir (survives archival). */
export async function addAnalysisToBoard(
  filePath: string,
  entry: AnalysisEntry,
  target?: BoardTarget,
  projectRoot?: string,
): Promise<string | null> {
  const norm = filePath.replace(/\\/g, '/')
  const stem = (norm.split('/').pop() ?? 'report').replace(/\.[^/.]+$/, '')
  const fileName = `${stem}.${entry.id}.md`
  const artifactPath =
    boardArtifactPath(projectRoot ?? '', fileName) || `${norm.replace(/\.[^/.]+$/, '')}.${entry.id}.md`
  const title = entry.title || 'Analysis report'
  return publishArtifactToBoard(
    norm,
    artifactPath,
    entry.content,
    `Report: ${title}`,
    'md',
    target,
  )
}
