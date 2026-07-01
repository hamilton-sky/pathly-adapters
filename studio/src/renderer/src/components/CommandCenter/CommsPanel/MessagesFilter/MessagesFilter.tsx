import { useRef, useState } from 'react'
import { Filter } from 'lucide-react'
import { Tooltip } from '../../../ui'
import type { MessageType } from '../../types'
import { FilterPopover } from './FilterPopover'
import s from './MessagesFilter.module.css'

interface Props {
  /** Selected types; empty = show all. */
  value: MessageType[]
  onChange: (types: MessageType[]) => void
}

// Filter the Messages thread by message type. A single icon trigger — with a count
// badge when a filter is applied — opens a popover of type chips (multi-select).
// Lives in the board view-toggle's right-action slot, on the Messages view only.
// 13 message types in one scroll is the board's real readability failure; this is
// the cheap fix, and it's the control that helps the narrow docked view most.
export function MessagesFilter({ value, onChange }: Props): JSX.Element {
  const btnRef = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useState(false)
  const active = value.length > 0

  return (
    <>
      <Tooltip label="Filter by type" description="Show only selected message types" placement="bottom">
        <button
          ref={btnRef}
          type="button"
          className={s.btn}
          aria-label="Filter by type"
          {...(active ? { 'data-active': '' } : {})}
          {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
          onClick={() => setOpen((v) => !v)}
        >
          <Filter size={14} />
          {active && <span className={s.count}>{value.length}</span>}
        </button>
      </Tooltip>
      {open && (
        <FilterPopover
          anchorEl={btnRef.current}
          value={value}
          onChange={onChange}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  )
}
