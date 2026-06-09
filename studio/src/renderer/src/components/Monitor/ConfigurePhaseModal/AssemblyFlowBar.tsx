import styles from './ConfigurePhaseModal.module.css'

interface Props { host: string; agent: string; skill: string }

export function AssemblyFlowBar({ host, agent, skill }: Props): JSX.Element {
  return (
    <div className={styles.flowBar}>
      <span className={styles.flowLabel}>host</span>
      <span className={`${styles.flowTag} ${styles.flowTagHost}`}>{host}</span>
      <span className={styles.flowArrow}>→</span>
      <span className={styles.flowLabel}>agent</span>
      <span className={`${styles.flowTag} ${styles.flowTagAgent}`}>{agent}</span>
      <span className={styles.flowArrow}>→</span>
      <span className={styles.flowLabel}>skill</span>
      <span className={`${styles.flowTag} ${styles.flowTagSkill}`}>{skill}</span>
      <span className={styles.flowArrow}>→</span>
      <span className={styles.flowHint}>prompt assembled</span>
    </div>
  )
}
