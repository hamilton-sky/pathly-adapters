import { useEffect, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { useFocusTrap } from '../../../hooks/useFocusTrap'
import s from './ConfirmModal.module.css'

interface Props {
  /** Heading — may include markup (e.g. a bolded name). */
  title: ReactNode
  /** Sub-line under the title. Defaults to the irreversibility warning. */
  message?: ReactNode
  /** Label on the confirm button. */
  confirmLabel?: string
  onCancel: () => void
  onConfirm: () => void
}

/**
 * Generic confirmation modal. Focus-trapped, Escape- and backdrop-dismissable,
 * portal-rendered to document.body. Reused by the sidebar delete flow and the
 * comms board message delete.
 */
export function ConfirmModal({
  title,
  message = 'This cannot be undone.',
  confirmLabel = 'Delete',
  onCancel,
  onConfirm,
}: Props): JSX.Element {
  const boxRef = useRef<HTMLDivElement>(null)
  useFocusTrap(boxRef)

  useEffect(() => {
    function onKey(e: KeyboardEvent): void { if (e.key === 'Escape') onCancel() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onCancel])

  return createPortal(
    <div
      className={s.overlay}
      onClick={(e) => { if (e.target === e.currentTarget) onCancel() }}
    >
      <div
        ref={boxRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-modal-title"
        className={s.box}
      >
        <p id="confirm-modal-title" className={s.title}>{title}</p>
        {message && <p className={s.sub}>{message}</p>}
        <div className={s.actions}>
          <button type="button" className={s.cancel} onClick={onCancel}>Cancel</button>
          <button type="button" className={s.confirm} onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
