import { useRef, useState } from 'react'
import { Plus } from 'lucide-react'
import { Tooltip, CreatePopover } from '../../../ui'
import s from './GoalsView.module.css'

interface Props {
  onCreate: (text: string) => void
}

// "+ New goal" trigger for the Goals board. Opens a create popover anchored under
// the button; on create it posts a type='goal' message, which starts with 0 tasks and
// a "Not planned" pill — planning is launched from the board's Evaluate control (target
// that goal). The label collapses to an icon (with this tooltip) when the panel is narrow.
export function NewGoalButton({ onCreate }: Props): JSX.Element {
  const btnRef = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useState(false)

  return (
    <>
      <Tooltip label="New goal" description="Create a goal on this board" placement="bottom">
        <button ref={btnRef} type="button" className={s.newGoalBtn} onClick={() => setOpen(true)}>
          <Plus size={13} />
          <span className={s.newGoalLabel}>New goal</span>
        </button>
      </Tooltip>
      {open && (
        <CreatePopover
          anchorEl={btnRef.current}
          heading="New goal"
          titleLabel="Goal"
          titlePlaceholder="e.g. Add OAuth login"
          descLabel="Details"
          descPlaceholder="Any context the planner should know before decomposing?"
          onSubmit={(title, desc) => { onCreate(desc ? `${title}\n\n${desc}` : title); setOpen(false) }}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  )
}
