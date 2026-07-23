import type { FragmentVM } from '../types'
import styles from './FragmentSplit.module.css'

interface Expand { isExpanded: (n: string) => boolean; toggle: (n: string) => void }
interface Props {
  included: FragmentVM[]
  available: FragmentVM[]
  expand: Expand
  onToggleFragment: (name: string) => void
}

/** Two-column layout: included stack (removable) ↔ available-to-add tray. Included rows expand inline. */
export function FragmentSplit({ included, available, expand, onToggleFragment }: Props): JSX.Element {
  const fragTokens = included.reduce((s, f) => s + f.tokens, 0)
  return (
    <div className={styles.grid}>
      <section className={styles.included}>
        <header className={styles.headIncl}>
          <i className={styles.dotGreen} />
          <span className={styles.title}>Included</span>
          <span className={styles.count}>{included.length}</span>
          <span className={styles.spacer} />
          <span className={styles.tok}>{fragTokens} tok</span>
        </header>
        <div className={styles.list}>
          {included.map((f) => {
            const open = expand.isExpanded(f.name)
            return (
              <div key={f.name} className={styles.card} data-open={open}>
                <div className={styles.cardRow}>
                  <span className={styles.order}>{f.order}</span>
                  <button type="button" className={styles.nameBtn} aria-expanded={open} onClick={() => expand.toggle(f.name)}>
                    <span className={styles.chev} data-open={open}>▸</span>
                    <span className={styles.nameText} data-open={open}>{f.name}</span>
                  </button>
                  <span className={styles.tokSm}>{f.tokens}</span>
                  <button type="button" className={styles.removeBtn} title="Remove" onClick={() => onToggleFragment(f.name)}>−</button>
                </div>
                {open && (
                  <div className={styles.detail}>
                    <p className={styles.detailText}>{f.purpose}</p>
                    <span className={styles.inject}>≈ {f.tokens} tok injected</span>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </section>

      <section className={styles.available}>
        <header className={styles.headAvail}>
          <i className={styles.dotMuted} />
          <span className={styles.titleMuted}>Available to add</span>
          <span className={styles.countMuted}>{available.length}</span>
        </header>
        <div className={styles.list}>
          {available.map((f) => (
            <div key={f.name} className={styles.availRow}>
              <span className={styles.availName}>{f.name}</span>
              <span className={styles.spacer} />
              <span className={styles.tokSm}>{f.tokens}</span>
              <button type="button" className={styles.addBtn} title="Add" onClick={() => onToggleFragment(f.name)}>+</button>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
