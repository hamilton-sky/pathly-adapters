import * as React from 'react'

/**
 * Pathly Select — native dropdown styled to match Input.
 */
export interface SelectOption {
  value: string
  label: string
}
export interface SelectProps {
  value: string
  onChange?: (e: React.ChangeEvent<HTMLSelectElement>) => void
  /** Array of {value,label} or plain strings */
  options: Array<SelectOption | string>
  /** @default "md" */
  size?: 'sm' | 'md'
  disabled?: boolean
  style?: React.CSSProperties
}

export function Select(props: SelectProps): JSX.Element
