// Builds the "Add to board" destination list for an editor artifact: Global, Project, and
// every known feature board, with the path-derived board (boardTargetForFile) marked
// `suggested` and hoisted to the top. Pure — the panel/hook feeds in the feature ids.

import { boardTargetForFile } from './boardArtifacts'
import type { BoardTarget, BoardTargetOption } from '../shared/AddToBoardButton/AddToBoardButton'

export function buildBoardTargets(
  sourceFile: string,
  featureIds: string[],
  projectRoot: string,
): BoardTargetOption[] {
  const root = projectRoot.replace(/\\/g, '/').replace(/\/$/, '')
  const suggested = boardTargetForFile(sourceFile)
  const isSuggested = (t: BoardTarget): boolean =>
    t.board === suggested.board && t.scope === suggested.scope

  const base: BoardTargetOption[] = [
    { key: 'global', label: 'Global', target: { feature: 'global', board: 'global', scope: 'global' } },
    { key: 'project', label: 'Project', target: { feature: 'project', board: 'project', scope: root } },
    ...featureIds.map((id) => ({
      key: `feature:${id}`,
      label: id,
      target: { feature: id, board: 'feature', scope: id },
    })),
  ]

  const marked = base.map((o) => (isSuggested(o.target) ? { ...o, suggested: true } : o))
  // Stable hoist: the suggested option first, everything else keeps its order.
  return [...marked.filter((o) => o.suggested), ...marked.filter((o) => !o.suggested)]
}
