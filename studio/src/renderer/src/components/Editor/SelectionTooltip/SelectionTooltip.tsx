import React, { useRef, useEffect } from 'react'
import { MessageSquarePlus } from 'lucide-react'
import styles from './SelectionTooltip.module.css'

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
        <MessageSquarePlus size={12} />
        Comment
      </button>
    </div>
  )
}
