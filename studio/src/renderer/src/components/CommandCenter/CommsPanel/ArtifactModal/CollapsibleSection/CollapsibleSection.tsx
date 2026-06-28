import { useState, type ReactNode } from 'react'
import { ChevronRight } from 'lucide-react'
import { CopyTextButton } from '../../../../shared/CopyTextButton/CopyTextButton'
import s from './CollapsibleSection.module.css'

interface Props {
  label: string
  /** Optional muted suffix after the label (e.g. the summary engine or preview line range). */
  hint?: string
  defaultOpen?: boolean
  /** When set, a copy-to-clipboard button appears in the banner that copies this text. */
  copyText?: string
  children: ReactNode
}

/**
 * A collapsible "banner" section: a header bar with a toggle button that opens/
 * closes its body, plus an optional copy-to-clipboard action. `label` is the
 * uppercase caption; `hint` is an optional muted suffix. Used in the artifact
 * modal for the AI Summary, Description, and Preview sections.
 */
export function CollapsibleSection({ label, hint, defaultOpen = true, copyText, children }: Props): JSX.Element {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <section className={s.section}>
      <div className={s.header}>
        <button
          type="button"
          className={s.banner}
          onClick={() => setOpen((v) => !v)}
          {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
        >
          <ChevronRight size={13} className={`${s.chevron} ${open ? s.chevronOpen : ''}`} />
          <span className={s.label}>{label}</span>
          {hint && <span className={s.hint}>{hint}</span>}
        </button>
        {copyText && <CopyTextButton text={copyText} label={label} />}
      </div>
      {open && <div className={s.content}>{children}</div>}
    </section>
  )
}
