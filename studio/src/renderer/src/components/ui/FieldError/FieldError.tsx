import styles from './FieldError.module.css'

interface FieldErrorProps {
  message?: string
}

export function FieldError({ message }: FieldErrorProps): JSX.Element | null {
  if (!message) return null
  return <span className={styles.root}>{message}</span>
}
