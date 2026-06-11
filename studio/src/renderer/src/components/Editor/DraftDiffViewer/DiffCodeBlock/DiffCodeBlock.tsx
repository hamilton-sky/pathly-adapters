import { useMemo } from 'react'
import { computeWordDiff, computeLineDiff } from '../diffUtils'
import styles from './DiffCodeBlock.module.css'

interface Props {
  original: string | null
  draft: string | null
  /** 'word' (default) highlights changed words inline — best for prose.
   *  'line' shows whole added/removed lines — best for code. */
  mode?: 'word' | 'line'
}

export function DiffCodeBlock({ original, draft, mode = 'word' }: Props): JSX.Element {
  const oneSided = original == null || draft == null

  if (mode === 'line') {
    return <LineDiff original={original} draft={draft} />
  }

  const tokens = useMemo(() => computeWordDiff(original, draft), [original, draft])

  return (
    <div>
      <div className={styles.root} aria-label="Diff">
        {tokens.map((tok, i) => {
          const isWhitespace = /^\s+$/.test(tok.text)
          if (tok.type === 'same' || isWhitespace) {
            return <span key={i}>{tok.text}</span>
          }
          return (
            <span key={i} className={tok.type === 'add' ? styles.tokenAdd : styles.tokenRemove}>
              {tok.text}
            </span>
          )
        })}
      </div>
      {!oneSided && (
        <div className={styles.legend}>
          <span><i className={styles.swatchRemove} />removed</span>
          <span><i className={styles.swatchAdd} />added</span>
        </div>
      )}
    </div>
  )
}

function LineDiff({ original, draft }: Pick<Props, 'original' | 'draft'>): JSX.Element {
  const lines = useMemo(() => computeLineDiff(original, draft), [original, draft])
  return (
    <div className={`${styles.root} ${styles.rootLines}`} aria-label="Code diff">
      {lines.map((line, i) => (
        <div
          key={i}
          className={`${styles.line} ${line.type === 'remove' ? styles.lineRemove : line.type === 'add' ? styles.lineAdd : styles.lineSame}`}
        >
          <span className={styles.prefix} aria-hidden="true">
            {line.type === 'remove' ? '−' : line.type === 'add' ? '+' : ' '}
          </span>
          <span className={styles.lineText}>{line.text || ' '}</span>
        </div>
      ))}
    </div>
  )
}
