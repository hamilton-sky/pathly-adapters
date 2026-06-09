import { Tooltip } from './Tooltip'
import styles from './IconButton.module.css'

interface IconButtonProps {
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void
  title: string
  description?: string
  shortcut?: string
  placement?: 'top' | 'bottom' | 'left' | 'right'
  children: React.ReactNode
  disabled?: boolean
  variant?: 'default' | 'danger' | 'muted'
  active?: boolean
  size?: 'sm' | 'md'
  'aria-expanded'?: 'true' | 'false'
  'data-testid'?: string
  'data-label'?: string
}

export function IconButton({
  onClick,
  title,
  description,
  shortcut,
  placement = 'bottom',
  children,
  disabled = false,
  variant,
  active = false,
  size,
  'aria-expanded': ariaExpanded,
  'data-testid': dataTestId,
  'data-label': dataLabel,
}: IconButtonProps): JSX.Element {
  const classNames = [
    styles.btn,
    variant === 'danger' ? styles.variantDanger : '',
    variant === 'muted' ? styles.variantMuted : '',
    size === 'md' ? styles.sizeMd : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <Tooltip label={title} description={description} shortcut={shortcut} placement={placement}>
      <button
        type="button"
        className={classNames}
        disabled={disabled}
        onClick={onClick}
        aria-label={title}
        data-testid={dataTestId}
        data-label={dataLabel}
        {...(active ? { 'data-active': 'true' } : {})}
        {...(ariaExpanded !== undefined ? { 'aria-expanded': ariaExpanded } : {})}
      >
        {children}
      </button>
    </Tooltip>
  )
}
