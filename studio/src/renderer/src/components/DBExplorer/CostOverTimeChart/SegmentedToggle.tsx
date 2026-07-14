import styles from './SegmentedToggle.module.css'

interface Option<T extends string | number> {
  label: string
  value: T
}

interface SegmentedToggleProps<T extends string | number> {
  options: Option<T>[]
  value: T
  onChange: (value: T) => void
  ariaLabel?: string
}

/** Generic segmented control — reused for the range (7d/14d/30d) and scale (Linear/Log) switches. */
export function SegmentedToggle<T extends string | number>({
  options,
  value,
  onChange,
  ariaLabel,
}: SegmentedToggleProps<T>): JSX.Element {
  return (
    <div className={styles.group} role="group" aria-label={ariaLabel}>
      {options.map((opt) => (
        <button
          key={String(opt.value)}
          type="button"
          className={styles.btn}
          {...(opt.value === value ? { 'data-active': '' } : {})}
          onClick={() => onChange(opt.value)}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}
