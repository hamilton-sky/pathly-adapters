// Pure board-key helpers shared by the store and its run watchers.
//
// `boardParamsForKey` in particular is centralized deliberately: the project board's DB scope
// is the project ROOT, not the literal 'project', and duplicating that rule is what previously
// broke posts, artifact drops, and board runs independently of each other.

import type { Message, BoardScope } from '../../components/CommandCenter/types'
import { scopeToParams } from '../commsApi'
import { useProjectStore } from '../projectStore'

export function isPending(m: Message): boolean {
  return (m.type === 'question' && m.status === 'pending')
    || (m.type === 'warning' && m.status === 'open')
    || m.type === 'escalation'
}

export function storageKey(scope: BoardScope, key: string): string {
  return scope === 'feature' ? key : scope
}

// Map a board KEY (a feature id, or the literal 'project'/'global') to its backend
// {board, scope}. The project board's DB scope is the project ROOT — what loadBoard
// and store.post read/write with — NOT the literal 'project', which the board never
// queries and which collides across projects in the shared central DB. Feature/global
// keys map straight through. Centralized so this project-scope trap can't recur (it
// already bit posts, artifact drops, and board runs separately).
export function boardParamsForKey(key: string): { board: string; scope: string } {
  const scope: BoardScope = key !== 'project' && key !== 'global' ? 'feature' : (key as BoardScope)
  if (scope === 'project') {
    const root = useProjectStore.getState().projectPath.replace(/\\/g, '/').replace(/\/$/, '')
    return scopeToParams(scope, root)
  }
  return scopeToParams(scope, key)
}
