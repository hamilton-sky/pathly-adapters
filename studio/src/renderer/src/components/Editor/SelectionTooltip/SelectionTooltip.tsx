import React, { useRef, useEffect } from 'react'
import { Sparkles } from 'lucide-react'
import { COMMENT_VERBS } from '../commentVerbs'
import styles from './SelectionTooltip.module.css'

// Derive the default action hint from the shared verb list (single source of truth).
const DEFAULT_VERB = COMMENT_VERBS[0]
const COMMENT_BUTTON_LABEL = DEFAULT_VERB.hint.split(' · ')[0] === 'default'
  ? 'Comment'
  : DEFAULT_VERB.label

interface Props {
  x: number
  y: number
  onComment: () => void
}

export function SelectionTooltip({ x, y, onComment }: Props): JSX.Element {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current) return
    ref.current.style.setProperty('--tip-x', `${x}px`)
    ref.current.style.setProperty('--tip-y', `${y}px`)
  }, [x, y])

  return (
    <div
      ref={ref}
      className={styles.tooltip}
      onMouseDown={(e) => e.stopPropagation()}
    >
      <button
        type="button"
        className={styles.btn}
        onClick={onComment}
        aria-label="Add comment on selection"
      >
        <Sparkles size={14} />
        {COMMENT_BUTTON_LABEL}
      </button>
    </div>
  )
}
