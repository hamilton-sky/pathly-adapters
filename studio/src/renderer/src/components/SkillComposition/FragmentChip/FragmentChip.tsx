import styles from './FragmentChip.module.css'

interface Props {
  kind: 'body' | 'fragment' | 'full'
  label: string
  included: boolean
  active: boolean
  onSelect: () => void
  onToggle?: () => void
}

/**
 * One chip in the fragment chip row. A `kind="fragment"` chip renders a small toggle
 * button (included/excluded, saved via the per-project override) alongside a label
 * button (click to select it for viewing). `body`/`full` chips are always "included"
 * (nothing to toggle) and only support selection.
 */
export function FragmentChip({ kind, label, included, active, onSelect, onToggle }: Props): JSX.Element {
  const toggleable = kind === 'fragment'

  return (
    <div className={styles.chip} data-kind={kind} data-included={included} data-active={active}>
      {toggleable && (
        <button
          type="button"
          className={styles.toggle}
          onClick={onToggle}
          aria-label={`${included ? 'Exclude' : 'Include'} ${label}`}
          {...(included ? { 'aria-pressed': 'true' } : { 'aria-pressed': 'false' })}
        >
          <span className={styles.dot} />
        </button>
      )}
      <button
        type="button"
        className={styles.label}
        onClick={onSelect}
        {...(active ? { 'aria-pressed': 'true' } : { 'aria-pressed': 'false' })}
      >
        {label}
      </button>
    </div>
  )
}
