import styles from './FlowTypeBadge.module.css'

interface Props { flowType: 'team' | 'debug' | 'explore' }

export function FlowTypeBadge({ flowType }: Props): JSX.Element {
  return <span className={styles.badge} data-flow={flowType}>{flowType}</span>
}
