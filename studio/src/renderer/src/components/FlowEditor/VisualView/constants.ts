import type { FlowExportTarget } from '../../../types'
import { StateNode } from './StateNode'
import { CommentNode } from './CommentNode'

export const nodeTypes = { stateNode: StateNode, commentNode: CommentNode }

export const EXPORT_TARGET_LABELS: Record<FlowExportTarget, string> = {
  'pathly-package': 'FSM Runtime',
  'claude-code': 'Claude Code',
  codex: 'Codex',
}

export const EXPORT_TARGET_DESCRIPTIONS: Record<FlowExportTarget, string> = {
  'pathly-package': 'This will overwrite the flow in src/pathly_data/core/flows/. The orchestrator will use this flow immediately.',
  'claude-code': 'This will write to .claude/pathly-flows/. Claude Code will pick up the flow on next session start.',
  codex: 'This will write to .codex/pathly-flows/. Codex will pick up the flow on next session start.',
}

export type PanelDetail =
  | null
  | { type: 'node'; stateId: string }
  | { type: 'edge'; edgeId: string; source: string; target: string }
