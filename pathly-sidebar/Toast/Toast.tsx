import styles from './Toast.module.css'

interface Props {
  message: string | null
}

/** Transient confirmation (e.g. "Copied …"). Renders nothing when empty. */
export function Toast({ message }: Props): JSX.Element | null {
  if (!message) return null
  return <div className={styles.toast}>{message}</div>
}
