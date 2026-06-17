import { useState } from 'react'
import { Plus } from 'lucide-react'
import { NewGoalModal } from './NewGoalModal'
import s from './GoalsView.module.css'

interface Props {
  onCreate: (text: string) => void
}

// "+ New goal" trigger for the Goals board. Opens the New goal modal; on create it
// posts a type='goal' message, which then shows its Decompose control (0 tasks),
// completing create → decompose → run.
export function NewGoalButton({ onCreate }: Props): JSX.Element {
  const [open, setOpen] = useState(false)

  return (
    <>
      <button type="button" className={s.newGoalBtn} onClick={() => setOpen(true)}>
        <Plus size={13} /> New goal
      </button>
      {open && (
        <NewGoalModal
          onCancel={() => setOpen(false)}
          onCreate={(text) => { onCreate(text); setOpen(false) }}
        />
      )}
    </>
  )
}
