import styles from './Toast.module.css'

/** Transient confirmation (e.g. "Copied …"). Renders nothing when empty. */
export function Toast({ message }: { message: string | null }): JSX.Element | null {
  if (!message) return null
  return <div className={styles.toast}>{message}</div>
}
