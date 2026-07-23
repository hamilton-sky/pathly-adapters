import type { DrawerDetail } from '../types'
import styles from './InspectDrawer.module.css'

interface Props {
  detail: DrawerDetail | null
  onClose: () => void
  onToggle: (fragment: string) => void
}

/** Slides up from the bottom of the composed pane (top stays fixed). Shows the inspected
 *  fragment / ability / system-prompt segment with its token cost + add/remove toggle. */
export function InspectDrawer({ detail, onClose, onToggle }: Props): JSX.Element {
  const open = !!detail
  return (
    <div className={styles.drawer} data-open={open}>
      {detail && (
        <div className={styles.inner}>
          <div className={styles.top}>
            <span className={styles.kind}>{detail.kindLabel}</span>
            <span className={styles.status} data-on={detail.on}>{detail.on ? 'included' : 'excluded'}</span>
            <span className={styles.spacer} />
            {detail.canToggle && detail.fragment && (
              <button type="button" className={styles.toggleBtn} onClick={() => onToggle(detail.fragment as string)}>
                {detail.on ? 'Remove from prompt' : 'Add to prompt'}
              </button>
            )}
            <button type="button" className={styles.close} title="Close" onClick={onClose}>✕</button>
          </div>
          <h1 className={styles.title}>{detail.title}</h1>
          <div className={styles.label}>Adds to prompt</div>
          <p className={styles.desc}>{detail.desc}</p>
          <div className={styles.stats}>
            <div className={styles.stat}><div className={styles.statLabel}>Token cost</div><div className={styles.statVal}>{detail.tokens}</div></div>
            <div className={styles.stat}><div className={styles.statLabel}>Source</div><div className={styles.statVal}>{detail.source}</div></div>
          </div>
        </div>
      )}
    </div>
  )
}
