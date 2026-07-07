import type { Message } from '../../types'
import { isMonitorMessage } from '../monitorClass'

export type BandKey = 'goals' | 'tasks' | 'messages' | 'artifacts'

export interface GridBands {
  goals: Message[]
  /** UNGROUPED tasks only — a task whose goal is on this board lives in that
   *  goal's DAG modal, not the flat Tasks band. */
  tasks: Message[]
  /** SIGNAL messages only — nudge, decision, question, answer, discovery,
   *  warning, escalation, note. Phase/lifecycle trace is split into `monitor`. */
  messages: Message[]
  /** Execution-trace noise (phase + supervisor/system status) — rendered in the
   *  collapsible Monitor lane, exactly like the Messages tab, not as tiles. */
  monitor: Message[]
  artifacts: Message[]
}

// Band order + labels live in one place so the view stays declarative.
export const BAND_ORDER: Array<{ key: BandKey; label: string; hint?: string }> = [
  { key: 'goals', label: 'Goals' },
  { key: 'tasks', label: 'Ungrouped tasks', hint: 'grouped tasks live inside their goal' },
  { key: 'messages', label: 'Messages' },
  { key: 'artifacts', label: 'Artifacts' },
]

// Pure, side-effect-free projection of the board array into kind-banded buckets.
// One pass; every item lands in exactly one band and nothing is silently dropped.
export function gridBands(messages: Message[]): GridBands {
  const goalIds = new Set<string>()
  for (const m of messages) if (m.type === 'goal') goalIds.add(m.id)

  const goals: Message[] = []
  const tasks: Message[] = []
  const msgs: Message[] = []
  const monitor: Message[] = []
  const artifacts: Message[] = []

  for (const m of messages) {
    if (m.type === 'goal') {
      goals.push(m)
    } else if (m.type === 'task') {
      // A task linked to a goal that IS on this board is "grouped" — it shows in
      // the goal's DAG, so keep it out of the flat band. Orphan/unknown-goal tasks
      // are the only ones the Tasks band surfaces.
      if (!m.goal_id || !goalIds.has(m.goal_id)) tasks.push(m)
    } else if (m.type === 'artifact') {
      artifacts.push(m)
    } else if (isMonitorMessage(m)) {
      // Phase boundaries + supervisor/system lifecycle status collapse into the
      // Monitor lane instead of flooding the Messages band with trace tiles.
      monitor.push(m)
    } else {
      msgs.push(m)
    }
  }

  return { goals, tasks, messages: msgs, monitor, artifacts }
}
