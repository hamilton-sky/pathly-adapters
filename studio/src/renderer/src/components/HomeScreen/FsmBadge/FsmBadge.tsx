import styles from './FsmBadge.module.css'

interface Props { state: string }

export function FsmBadge({ state }: Props): JSX.Element {
  const s = state.toUpperCase()
  const label = state.charAt(0).toUpperCase() + state.slice(1).toLowerCase()

  if (!s || s === 'IDLE') return <span className={styles.dot} title="Idle" />

  let variant: string
  if (s === 'DONE') variant = 'done'
  else if (s === 'BLOCKED') variant = 'blocked'
  else if (s === 'BUILDING' || s === 'REVIEWING' || s === 'COMMITTING') variant = 'active'
  else if (s === 'PLANNING' || s === 'STORMING') variant = 'planning'
  else variant = 'default'

  return <span className={styles.badge} data-state={variant}>{s === 'DONE' ? 'Done' : label}</span>
}
