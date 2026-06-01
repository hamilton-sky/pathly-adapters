import { Tooltip } from '../../ui'
import styles from './FlowControlBar.module.css'

interface RunnerBtnProps {
  label: string
  tooltip: string
  enabled: boolean
  onClick: () => void
  extraClass?: string
  abortStyle?: boolean
  children: React.ReactNode
}

export function RunnerBtn({
  label,
  tooltip,
  enabled,
  onClick,
  extraClass = '',
  abortStyle = false,
  children,
}: RunnerBtnProps): JSX.Element {
  const cls = [
    styles.btn,
    abortStyle ? styles.btnAbort : '',
    extraClass,
    !enabled ? styles.btnDisabled : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <Tooltip label={tooltip} placement="bottom">
      <button
        type="button"
        className={cls}
        disabled={!enabled}
        aria-label={label}
        {...(enabled ? { 'aria-disabled': 'false' } : { 'aria-disabled': 'true' })}
        onClick={onClick}
      >
        {children}
      </button>
    </Tooltip>
  )
}
