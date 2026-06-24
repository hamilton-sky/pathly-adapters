import { useState } from 'react'
import { ChevronRight } from 'lucide-react'
import styles from './CommentAnchor.module.css'

interface Props {
  text: string
}

/**
 * Collapsible banner showing the text the comment is anchored to.
 * Collapsed (default): a single truncated line. Expanded: the full selection.
 */
export function CommentAnchor({ text }: Props): JSX.Element {
  const [open, setOpen] = useState(false)
  const preview = text.length > 80 ? text.slice(0, 80).trimEnd() + '…' : text.trim()

  return (
    <div className={styles.wrap}>
      <button
        type="button"
        className={styles.toggle}
        onClick={() => setOpen((o) => !o)}
        {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
      >
        <ChevronRight size={12} className={styles.chevron} />
        <span className={styles.preview}>{open ? 'Selected text' : `"${preview}"`}</span>
      </button>
      {open && <div className={styles.full}>&quot;{text}&quot;</div>}
    </div>
  )
}
