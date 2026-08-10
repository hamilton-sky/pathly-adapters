import { useState } from 'react'
import { Plus } from 'lucide-react'
import { useStore } from '../../../../store'
import { NewRunModal } from './NewRunModal'
import s from './NewRunButton.module.css'

interface Props {
  /** Called after a run is created so the caller can refresh its run list. */
  onCreated: () => void
}

// "New run" launcher (unified-control-plane T6) — Runs-mode toolbar trigger for the unified
// POST /runs launcher (backend T5). This component just owns open/close and the project/scope
// defaults (activeTopic — same "current feature" concept the rest of the Monitor panel uses);
// NewRunModal owns the dialog shell and NewRunForm owns the fields + submit.
export function NewRunButton({ onCreated }: Props): JSX.Element {
  const [open, setOpen] = useState(false)
  const projectPath = useStore((st) => st.projectPath)
  const activeTopic = useStore((st) => st.activeTopic)

  return (
    <>
      <button type="button" className={s.trigger} onClick={() => setOpen(true)}>
        <Plus size={13} /> New run
      </button>

      {open && (
        <NewRunModal
          projectRoot={projectPath}
          defaultScope={activeTopic ?? ''}
          onClose={() => setOpen(false)}
          onCreated={() => { setOpen(false); onCreated() }}
        />
      )}
    </>
  )
}
