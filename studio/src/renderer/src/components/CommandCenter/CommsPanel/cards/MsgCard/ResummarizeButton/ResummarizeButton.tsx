import { useState } from 'react'
import { RotateCw } from 'lucide-react'
import { useStore } from '../../../../../../store'
import { useToastStore } from '../../../../../../store/toastStore'
import { resummarizeArtifactByMessage } from '../../../ArtifactsView/summarizeArtifact'
import s from './ResummarizeButton.module.css'

// Per-artifact Re-summarize affordance (unified-ai-routing Conv 3, DESIGN.md).
// Re-runs the artifact's saved AI target (or the app default) through aiRouter and
// writes the result back. data-state drives the chip decoration: idle / running /
// error. The board's COMMS_UPDATE summary_ready (broadcast by the writeback route)
// refreshes the card, so this button owns only its own in-flight/error state.

interface Props {
  /** The artifact message id (resolves to its comms_artifacts row + saved target). */
  messageId: string
}

export function ResummarizeButton({ messageId }: Props): JSX.Element {
  const [state, setState] = useState<'idle' | 'running' | 'error'>('idle')
  const projectPath = useStore((st) => st.projectPath)

  async function handleClick(): Promise<void> {
    if (state === 'running') return
    setState('running')
    const cwd = projectPath.replace(/\\/g, '/').replace(/\/$/, '') || undefined
    const outcome = await resummarizeArtifactByMessage(messageId, cwd)
    const push = useToastStore.getState().push
    if (outcome === 'ok') {
      setState('idle')
    } else if (outcome === 'skipped') {
      setState('idle')
      push('No summary target set for this artifact — pick one above', 'info', { category: 'db_crud' })
    } else {
      setState('error')
      push('Re-summarize failed', 'error', { category: 'runner_state' })
      window.setTimeout(() => setState('idle'), 2500)
    }
  }

  return (
    <button
      type="button"
      className={s.btn}
      data-state={state}
      aria-label="Re-summarize"
      title="Re-summarize this artifact"
      disabled={state === 'running'}
      onClick={() => void handleClick()}
    >
      <RotateCw size={11} className={state === 'running' ? s.spin : undefined} />
    </button>
  )
}
