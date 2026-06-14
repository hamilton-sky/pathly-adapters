import { ReactNode } from 'react'
import styles from './SectionLabel.module.css'

/** Uppercase section label with a trailing divider rule (WORKSPACE ────). */
export function SectionLabel({ children }: { children: ReactNode }): JSX.Element {
  return <div className={styles.label}>{children}</div>
}
