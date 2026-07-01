import type { MessageType } from '../../types'

export interface FilterGroup {
  label: string
  types: MessageType[]
}

// Thread-eligible message types, grouped by role for a scannable filter popover.
// goal/task are excluded — they live in the "Goals & Tasks" view, never the thread
// (see CommsMsgList, which filters them out).
export const FILTER_GROUPS: FilterGroup[] = [
  { label: 'Conversation', types: ['nudge', 'decision', 'question', 'answer'] },
  { label: 'Knowledge', types: ['discovery', 'note', 'artifact'] },
  { label: 'Status', types: ['status', 'phase'] },
  { label: 'Signals', types: ['warning', 'escalation'] },
]

// Flat list of every filterable type — for counts / "all" checks.
export const FILTERABLE_TYPES: MessageType[] = FILTER_GROUPS.flatMap((g) => g.types)
