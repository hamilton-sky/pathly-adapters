import type { PreviewRowVM, PreviewTab } from '../types'
import styles from './FragmentListPanel.module.css'

interface Props {
  tab: PreviewTab
  onTab: (t: PreviewTab) => void
  rows: PreviewRowVM[]
  activeId: string | null
  activeCount: number
  totalCount: number
  onToggle: (fragment: string) => void
  onInspect: (row: PreviewRowVM) => void
}

const TABS: { id: PreviewTab; label: string }[] = [
  { id: 'fragments', label: 'Fragments' },
  { id: 'abilities', label: 'Abilities' },
  { id: 'system', label: 'System' },
]

/** Left tabbed list: Fragments / Abilities / System. Checkbox toggles inclusion; the eye inspects. */
export function FragmentListPanel({ tab, onTab, rows, activeId, activeCount, totalCount, onToggle, onInspect }: Props): JSX.Element {
  return (
    <div className={styles.panel}>
      <div className={styles.tabs} role="tablist">
        {TABS.map((t) => (
          <button key={t.id} type="button" role="tab" aria-selected={tab === t.id} data-active={tab === t.id} className={styles.tab} onClick={() => onTab(t.id)}>{t.label}</button>
        ))}
      </div>
      <div className={styles.countRow}>
        <span className={styles.countOn}>{activeCount}</span>
        <span className={styles.countTotal}>/ {totalCount} active</span>
        <span className={styles.spacer} />
        <span className={styles.hint}>✓ toggle · ◉ inspect</span>
      </div>
      <div className={styles.list}>
        {rows.map((r) => {
          const active = r.id === activeId
          return (
            <div key={r.id} className={styles.row} data-active={active} data-on={r.on}>
              {r.hasCheck ? (
                <button type="button" className={styles.check} data-on={r.on} aria-label={'Toggle ' + r.label} onClick={() => r.fragment && onToggle(r.fragment)}>✓</button>
              ) : (
                <span className={styles.lock} title="Always present">◆</span>
              )}
              <span className={styles.name}>{r.label}</span>
              <span className={styles.trail}>{r.trail}</span>
              <button type="button" className={styles.eye} data-active={active} title="Inspect" onClick={() => onInspect(r)}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" /><circle cx="12" cy="12" r="3" />
                </svg>
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}
