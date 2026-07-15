import { Check, Plus } from 'lucide-react'
import styles from './CompositionStep.module.css'

interface Props {
  kind: 'body' | 'fragment' | 'result'
  name: string
  order?: number
  purpose?: string
  included: boolean
  tokensLabel?: string
  onToggle?: () => void
  onSelect?: () => void
}

/**
 * One row in the composition "recipe": an ordered marker on a connector rail, the fragment
 * name (clickable to inspect it in Preview), its one-line purpose, and — for a fragment — an
 * include/exclude toggle. `body` and `result` rows are structural (no toggle).
 */
export function CompositionStep({
  kind,
  name,
  order,
  purpose,
  included,
  tokensLabel,
  onToggle,
  onSelect,
}: Props): JSX.Element {
  const marker = kind === 'result' ? '✦' : kind === 'body' ? '▚' : order != null ? String(order) : '+'

  return (
    <div className={styles.step} data-kind={kind} data-included={included}>
      <div className={styles.rail}>
        <span className={styles.marker}>{marker}</span>
      </div>
      <div className={styles.main}>
        <div className={styles.top}>
          {onSelect ? (
            <button type="button" className={styles.name} onClick={onSelect}>
              {name}
            </button>
          ) : (
            <span className={styles.name} data-static="true">
              {name}
            </span>
          )}
          {tokensLabel && <span className={styles.tokens}>{tokensLabel}</span>}
          {onToggle && (
            <button
              type="button"
              className={styles.toggle}
              data-included={included}
              onClick={onToggle}
              aria-label={`${included ? 'Exclude' : 'Include'} ${name}`}
              {...(included ? { 'aria-pressed': 'true' } : { 'aria-pressed': 'false' })}
            >
              {included ? <Check size={12} /> : <Plus size={12} />}
              <span className={styles.toggleLabel}>{included ? 'included' : 'add'}</span>
            </button>
          )}
        </div>
        {purpose && <div className={styles.purpose}>{purpose}</div>}
      </div>
    </div>
  )
}
