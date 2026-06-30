// "Add to board" for a single diagram — USER-triggered, renderer-side (the generating agent
// never posts). Exports the diagram's source to a sibling file and posts it as a comms
// artifact. The card stays — this is a copy, not a move. (Board-side inline rendering of the
// artifact is a follow-up that reuses DiagramRender.)

import { publishArtifactToBoard } from '../boardArtifacts'
import type { DiagramEntry } from '../diagramTypes'
import type { BoardTarget } from '../../shared/AddToBoardButton/AddToBoardButton'

const EXT: Record<DiagramEntry['style'], string> = {
  mermaid: 'mmd',
  ascii: 'txt',
  plantuml: 'puml',
}

/** Returns the new board message id, or null on failure. `target` is the user's board pick. */
export async function addDiagramToBoard(
  filePath: string,
  entry: DiagramEntry,
  target?: BoardTarget,
): Promise<string | null> {
  const norm = filePath.replace(/\\/g, '/')
  const ext = EXT[entry.style] ?? 'txt'
  const base = norm.replace(/\.[^/.]+$/, '')
  const artifactPath = `${base}.${entry.id}.${ext}`
  const title = entry.title || `${entry.style} diagram`
  return publishArtifactToBoard(
    norm,
    artifactPath,
    entry.content,
    `Diagram: ${title} (${entry.style})`,
    ext,
    target,
  )
}
