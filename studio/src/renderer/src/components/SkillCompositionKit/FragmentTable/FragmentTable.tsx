import type { FragmentVM } from '../types'
import { BODY_TOKENS } from '../data/systemPrompt'
import styles from './FragmentTable.module.css'

interface Expand { isExpanded: (n: string) => boolean; toggle: (n: string) => void }
interface Props { included: FragmentVM[]; expand: Expand; onToggleFragment: (name: string) => void }

/** Dense table layout (order · fragment · adds · tokens · toggle). Rows expand inline. */
export function FragmentTable({ included, expand, onToggleFragment }: Props): JSX.Element {
  return (
    <div className={styles.table}>
      <div className={styles.headRow}>
        <span className={styles.colNum}>#</span>
        <span className={styles.colName}>Fragment</span>
        <span className={styles.colAdds}>Adds to prompt</span>
        <span className={styles.colTok}>Tokens</span>
        <span className={styles.colToggle} />
      </div>

      <div className={styles.bodyRow}>
        <span className={styles.colNum} data-mono>—</span>
        <span className={styles.colName} data-mono data-strong>Skill body</span>
        <span className={styles.colAdds}>Base role, context files and run protocol.</span>
        <span className={styles.colTok} data-mono>{BODY_TOKENS}</span>
        <span className={styles.colToggle} data-required>required</span>
      </div>

      {included.map((f) => {
        const open = expand.isExpanded(f.name)
        return (
          <div key={f.name} className={styles.rowWrap}>
            <div className={styles.row}>
              <span className={styles.colNum} data-mono data-green>{f.order}</span>
              <button type="button" className={styles.nameBtn} aria-expanded={open} onClick={() => expand.toggle(f.name)}>
                <span className={styles.chev} data-open={open}>▸</span>
                <span className={styles.nameText} data-open={open}>{f.name}</span>
              </button>
              <span className={styles.colAdds}>{f.purpose}</span>
              <span className={styles.colTok} data-mono>{f.tokens}</span>
              <span className={styles.colToggle}>
                <button type="button" className={styles.onBtn} onClick={() => onToggleFragment(f.name)}>✓ on</button>
              </span>
            </div>
            {open && (
              <div className={styles.detail}>
                <div className={styles.detailLabel}>Adds to prompt</div>
                <p className={styles.detailText}>{f.purpose}</p>
                <div className={styles.detailFoot}>
                  <span className={styles.inject}>≈ {f.tokens} tok injected</span>
                </div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
