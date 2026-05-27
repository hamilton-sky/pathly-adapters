import { useState, useEffect } from 'react'
import { ChevronDown } from 'lucide-react'
import styles from './ThinkingBlock.module.css'

interface Props {
  thinking: string
  status: 'idle' | 'streaming' | 'done'
}

export function ThinkingBlock({ thinking, status }: Props): JSX.Element | null {
  const [expanded, setExpanded] = useState(true)

  // Auto-collapse 800ms after streaming ends
  useEffect(() => {
    if (status === 'done') {
      const t = setTimeout(() => setExpanded(false), 800)
      return () => clearTimeout(t)
    }
    // Re-open if a new stream starts (e.g. message reused)
    setExpanded(true)
  }, [status])

  if (!thinking) return null

  return (
    <div className={styles.container}>
      <button
        className={styles.toggle}
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
        aria-label={expanded ? 'Collapse reasoning' : 'Expand reasoning'}
      >
        <span className={styles.label}>
          {status === 'streaming' ? 'Thinking…' : 'Reasoning'}
        </span>
        <ChevronDown
          size={12}
          className={`${styles.chevron} ${expanded ? styles.chevronOpen : ''}`}
        />
      </button>
      <div className={`${styles.bodyWrapper} ${expanded ? '' : styles.collapsed}`}>
        <div className={styles.body}>{thinking}</div>
      </div>
    </div>
  )
}
