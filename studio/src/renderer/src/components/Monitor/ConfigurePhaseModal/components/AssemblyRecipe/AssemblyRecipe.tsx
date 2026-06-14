import { Check } from 'lucide-react'
import styles from './AssemblyRecipe.module.css'

interface AssemblyRecipeProps {
  host: string
  agent: string
  skill: string
}

/** Read-only “recipe” strip: host → agent → skill → prompt assembled. */
export function AssemblyRecipe({ host, agent, skill }: AssemblyRecipeProps): JSX.Element {
  return (
    <div className={styles.recipe}>
      <span className={styles.key}>host</span>
      <span className={`${styles.tag} ${styles.host}`}>{host}</span>
      <span className={styles.arrow}>→</span>

      <span className={styles.key}>agent</span>
      <span className={`${styles.tag} ${styles.agent}`}>{agent}</span>
      <span className={styles.arrow}>→</span>

      <span className={styles.key}>skill</span>
      <span className={`${styles.tag} ${styles.skill}`}>{skill}</span>
      <span className={styles.arrow}>→</span>

      <span className={styles.done}>
        <Check size={12} />
        prompt assembled
      </span>
    </div>
  )
}
