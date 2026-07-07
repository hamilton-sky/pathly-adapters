import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import type { Message } from '../../types'
import { MsgCard } from '../cards/MsgCard/MsgCard'
import { useFocusTrap } from '../../../../hooks/useFocusTrap'
import s from './MessageDetailModal.module.css'

interface Props {
  message: Message
  siblings: Message[]
  onClose: () => void
}

// Lightweight detail modal for a plain message tile — wraps the canonical MsgCard
// in a portal + backdrop + focus trap so the detail view always matches the thread.
// Read-only on purpose: no action handlers are passed, so MsgCard renders no
// delete / supersede / answer / resolve controls (the All tab is an overview).
export function MessageDetailModal({ message, siblings, onClose }: Props): JSX.Element {
  const boxRef = useRef<HTMLDivElement>(null)
  useFocusTrap(boxRef)

  useEffect(() => {
    function onKey(e: KeyboardEvent): void {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return createPortal(
    <div className={s.backdrop} onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div ref={boxRef} role="dialog" aria-modal="true" aria-label="Message details" className={s.box}>
        <button type="button" className={s.close} onClick={onClose} aria-label="Close">
          <X size={15} />
        </button>
        <MsgCard message={message} flash={false} siblings={siblings} />
      </div>
    </div>,
    document.body,
  )
}
