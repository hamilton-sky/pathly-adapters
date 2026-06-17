import { useState } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import type { FlowDef } from '../flowCatalog'
import s from './FlowAbout.module.css'

interface Props {
  flow: FlowDef
}

// Collapsible "About this flow" disclosure shown under the diagram — richer
// per-flow guidance (when to use it, what it produces) the user expands on demand.
// Open state persists across flow changes so details can be compared.
export function FlowAbout({ flow }: Props): JSX.Element {
  const [open, setOpen] = useState(false)
  return (
    <div className={s.about}>
      <button
        type="button"
        className={s.toggle}
        {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
        onClick={() => setOpen((o) => !o)}
      >
        {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        <span className={s.toggleLabel}>About this flow</span>
      </button>
      {open && (
        <dl className={s.details}>
          {flow.details.map((d) => (
            <div key={d.label} className={s.detail}>
              <dt className={s.dt}>{d.label}</dt>
              <dd className={s.dd}>{d.text}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  )
}
