import { ReactNode } from 'react'
import styles from './ChipGroup.module.css'
import { SectionLabel } from '../SectionLabel/SectionLabel'
import { Chip } from '../Chip/Chip'
import { AddChip } from '../AddChip/AddChip'
import type { ChipVariant } from '../../types'

interface ChipGroupProps {
  label: string
  options: string[]
  value: string
  variant: ChipVariant
  mono?: boolean
  onSelect: (value: string) => void
  /** When provided, renders a trailing “+ add” affordance. */
  onAdd?: () => void
  /** Arbitrary trailing node in the chip row (e.g. a catalog dropdown). */
  trailing?: ReactNode
}

/**
 * A labelled, single-select row of chips (CLI Host / Agent / Skill).
 * If `value` isn't in `options` it's shown as a trailing selected custom chip.
 */
export function ChipGroup({
  label,
  options,
  value,
  variant,
  mono,
  onSelect,
  onAdd,
  trailing,
}: ChipGroupProps): JSX.Element {
  const hasCustomValue = !options.includes(value)

  return (
    <div>
      <SectionLabel>{label}</SectionLabel>
      <div className={styles.chips}>
        {options.map((option) => (
          <Chip
            key={option}
            variant={variant}
            mono={mono}
            selected={option === value}
            onClick={() => onSelect(option)}
          >
            {option}
          </Chip>
        ))}
        {hasCustomValue && (
          <Chip variant={variant} mono={mono} selected>
            {value}
          </Chip>
        )}
        {onAdd && <AddChip onClick={onAdd} />}
        {trailing}
      </div>
    </div>
  )
}
