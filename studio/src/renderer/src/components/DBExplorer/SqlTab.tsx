import styles from './SqlTab.module.css'

export function SqlTab(): JSX.Element {
  return (
    <div className={styles.container}>
      <p className={styles.sublabel}>SQL Console</p>
      <div className={styles.placeholder}>
        <span className={styles.icon}>⊞</span>
        <span className={styles.message}>SQL console coming soon</span>
        <span className={styles.sub}>Run queries directly against the pipeline database</span>
      </div>
    </div>
  )
}
