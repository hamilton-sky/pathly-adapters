import { useState } from 'react'
import { Check, CheckCircle2 } from 'lucide-react'
import { markFeatureDone } from '../../../services/pathlyApi'
import s from './MarkDoneButton.module.css'

type Phase = 'idle' | 'confirm' | 'busy' | 'done'

/**
 * Feature-level "Mark done" — a manual override for goal-driven features whose FSM
 * never auto-advanced (work ran under goal boards, so the feature sat at STORMING).
 * Always available by design: it does NOT gate itself on goal/task completion, because
 * that same tracking is what tends to be out of sync — the override has to work then.
 * Two-click confirm (idle → "Confirm?" → POST) so it can't fire by accident; on success
 * it flips to a persistent "Done" pill. A board reload re-hydrates the real DB state.
 */
export function MarkDoneButton({
  feature,
  projectPath,
}: {
  feature: string
  projectPath: string
}): JSX.Element {
  const [phase, setPhase] = useState<Phase>('idle')

  async function onClick(): Promise<void> {
    if (phase === 'idle') {
      setPhase('confirm')
      return
    }
    if (phase !== 'confirm') return
    setPhase('busy')
    try {
      await markFeatureDone(projectPath, feature)
      setPhase('done')
    } catch {
      setPhase('idle')
    }
  }

  if (phase === 'done') {
    return (
      <span className={s.done} title={`${feature} marked DONE`}>
        <CheckCircle2 size={13} /> Done
      </span>
    )
  }

  return (
    <button
      type="button"
      className={s.btn}
      {...(phase === 'confirm' ? { 'data-confirm': '' } : {})}
      disabled={phase === 'busy'}
      title="Mark this feature DONE"
      onClick={onClick}
      onBlur={() => setPhase((p) => (p === 'confirm' ? 'idle' : p))}
    >
      <Check size={13} />
      {phase === 'confirm' ? 'Confirm?' : phase === 'busy' ? '…' : 'Mark done'}
    </button>
  )
}
