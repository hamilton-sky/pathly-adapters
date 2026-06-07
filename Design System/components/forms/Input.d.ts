import * as React from 'react'

/**
 * Pathly Input — single-line text field with optional leading icon and label.
 */
export interface InputProps {
  value: string
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void
  placeholder?: string
  /** Uppercase field label rendered above the input */
  label?: string
  /** Leading icon node */
  icon?: React.ReactNode
  /** @default "md" */
  size?: 'sm' | 'md'
  disabled?: boolean
  type?: string
  onKeyDown?: (e: React.KeyboardEvent<HTMLInputElement>) => void
  style?: React.CSSProperties
}

export function Input(props: InputProps): JSX.Element
