import React from 'react'
import { Tooltip } from '../ui'
import styles from './TopBar.module.css'

/** Corner brand mark — clicking returns to the project picker (home). */
export function PathlyLogo({ onHome }: { onHome: () => void }): JSX.Element {
  return (
    <Tooltip label="Back to home" placement="bottom">
      <button type="button" className={styles.logoBtn} onClick={onHome} aria-label="Back to home">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          {/* Pathly flow mark: two nodes joined by a branching path */}
          <path d="M6 18V9a3 3 0 0 1 3-3h6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          <circle cx="6" cy="18" r="2.4" fill="currentColor" />
          <circle cx="18" cy="6" r="2.4" fill="currentColor" />
        </svg>
      </button>
    </Tooltip>
  )
}
