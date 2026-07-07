import type { Message } from '../types'

// FSM phase boundaries (`phase`) + supervisor/system lifecycle status
// (`Started:/Done:`, goal-run started/finished) are execution-trace noise, not
// semantic signal — they belong in the collapsible Monitor lane, never inline as
// cards or tiles. Shared by the Messages list (CommsMsgList) and the All grid
// (GridView) so both surfaces agree on exactly what counts as trace.
export function isMonitorMessage(m: Message): boolean {
  return (
    m.type === 'phase' ||
    (m.type === 'status' && (m.from === 'supervisor' || m.from === 'system'))
  )
}
