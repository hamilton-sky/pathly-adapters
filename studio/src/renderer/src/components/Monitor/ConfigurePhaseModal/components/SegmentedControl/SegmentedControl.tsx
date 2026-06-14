import styles from './SegmentedControl.module.css'

interface SegmentedOption<T extends string> {
  value: T
  label: string
  disabled?: boolean
}

interface SegmentedControlProps<T extends string> {
  options: SegmentedOption<T>[]
  value: T
  onChange: (value: T) => void
  /** `sm` tightens padding (used inside dense headers). */
  size?: 'sm' | 'md'
}

/** Generic pill segmented control for 2–3 short, mutually-exclusive options. */
export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  size = 'md',
}: SegmentedControlProps<T>): JSX.Element {
  return (
    <div className={`${styles.seg} ${size === 'sm' ? styles.sm : ''}`}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={`${styles.btn} ${option.value === value ? styles.active : ''}`}
          disabled={option.disabled}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
