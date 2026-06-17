import { useState } from 'react'
import { Plus } from 'lucide-react'
import { Tooltip } from '../../../ui'
import { NewGoalModal } from './NewGoalModal'
import s from './GoalsView.module.css'

interface Props {
  onCreate: (text: string) => void
}

// "+ New goal" trigger for the Goals board. Opens the New goal modal; on create it
// posts a type='goal' message, which then shows its Decompose control (0 tasks),
// completing create → decompose → run. The label collapses to an icon (with this
// tooltip) when the panel is narrow.
export function NewGoalButton({ onCreate }: Props): JSX.Element {
  const [open, setOpen] = useState(false)

  return (
    <>
      <Tooltip label="New goal" description="Create a goal on this board" placement="bottom">
        <button type="button" className={s.newGoalBtn} onClick={() => setOpen(true)}>
          <Plus size={13} />
          <span className={s.newGoalLabel}>New goal</span>
        </button>
      </Tooltip>
      {open && (
        <NewGoalModal
          onCancel={() => setOpen(false)}
          onCreate={(text) => { onCreate(text); setOpen(false) }}
        />
      )}
    </>
  )
}
