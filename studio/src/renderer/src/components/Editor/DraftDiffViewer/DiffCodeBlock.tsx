import { useMemo } from 'react'
import { computeLineDiff } from './diffUtils'
import styles from './DiffCodeBlock.module.css'

interface Props {
  original: string | null
  draft: string | null
}

export function DiffCodeBlock({ original, draft }: Props): JSX.Element {
  const lines = useMemo(() => computeLineDiff(original, draft), [original, draft])

  return (
    <div className={styles.root} aria-label="Code diff">
      {lines.map((line, i) => (
        <div
          key={i}
          className={`${styles.line} ${line.type === 'remove' ? styles.lineRemove : line.type === 'add' ? styles.lineAdd : styles.lineSame}`}
        >
          <span className={styles.prefix} aria-hidden="true">
            {line.type === 'remove' ? '−' : line.type === 'add' ? '+' : ' '}
          </span>
          <span className={styles.text}>{line.text || ' '}</span>
        </div>
      ))}
    </div>
  )
}
