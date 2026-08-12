import type { MessageType } from '../../types'

export interface FilterGroup {
  label: string
  types: MessageType[]
}

// Thread-eligible message types, grouped by role for a scannable filter popover.
// goal/task/artifact are excluded — they live in their own board views (Goals &
// Tasks, Artifacts), never the message thread (see CommsMsgList, which filters them out).
export const FILTER_GROUPS: FilterGroup[] = [
  { label: 'Conversation', types: ['nudge', 'decision', 'question', 'answer'] },
  { label: 'Knowledge', types: ['discovery', 'note'] },
  { label: 'Status', types: ['status', 'phase'] },
  { label: 'Signals', types: ['warning', 'escalation'] },
]

// Flat list of every filterable type — for counts / "all" checks.
const FILTERABLE_TYPES: MessageType[] = FILTER_GROUPS.flatMap((g) => g.types)
