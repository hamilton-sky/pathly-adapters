// The boardKey convention — how a (scope, key) pair becomes the board/scope query params
// every /comms endpoint expects. One definition, because getting it wrong silently posts to
// the wrong board.

import type { BoardScope } from '../../components/CommandCenter/types'

export function scopeToParams(scope: BoardScope, key: string): { board: string; scope: string } {
  if (scope === 'feature') return { board: 'feature', scope: key }
  if (scope === 'project') return { board: 'project', scope: key.replace(/\\/g, '/').replace(/\/$/, '') }
  return { board: 'global', scope: 'global' }
}
