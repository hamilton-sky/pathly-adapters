import { ReactNode, MouseEvent } from 'react'
import { createPortal } from 'react-dom'
import styles from './Modal.module.css'

interface ModalProps {
  children: ReactNode
  onClose: () => void
  ariaLabel?: string
  /** Dialog width in px. Default 780. */
  width?: number
}

/**
 * Generic centered modal shell: scrim + dialog surface + brand hairline.
 * Closes on backdrop click and renders into <body> via a portal.
 */
export function Modal({ children, onClose, ariaLabel, width = 780 }: ModalProps): JSX.Element {
  function handleBackdrop(e: MouseEvent<HTMLDivElement>): void {
    if (e.target === e.currentTarget) onClose()
  }

  return createPortal(
    <div className={styles.backdrop} onClick={handleBackdrop}>
      <div
        className={styles.modal}
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel}
        style={{ width }}
      >
        {children}
      </div>
    </div>,
    document.body,
  )
}
