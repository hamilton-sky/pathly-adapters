import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { useFocusTrap } from '../../../../hooks/useFocusTrap'
import { NewRunForm } from './NewRunForm'
import s from './NewRunButton.module.css'

interface Props {
  projectRoot: string
  defaultScope: string
  onClose: () => void
  onCreated: () => void
}

// Modal shell for the New-run launcher (T6) — mirrors ConfirmModal's dismiss behavior (backdrop
// click, Escape, focus trap, portal-rendered to <body>) with the board Run modal's
// header/body/footer look (SingleAgentButton). Freshly mounted each time NewRunButton opens it,
// so the focus trap's effect (keyed on a stable ref) always attaches to the current dialog.
export function NewRunModal({ projectRoot, defaultScope, onClose, onCreated }: Props): JSX.Element {
  const boxRef = useRef<HTMLDivElement>(null)
  useFocusTrap(boxRef)

  useEffect(() => {
    function onKey(e: KeyboardEvent): void { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return createPortal(
    <div className={s.backdrop} onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div ref={boxRef} className={s.modal} role="dialog" aria-modal="true" aria-label="Start a new run">
        <header className={s.header}>
          <span className={s.title}>New run</span>
          <span className={s.spacer} />
          <button type="button" className={s.closeBtn} onClick={onClose} aria-label="Close">
            <X size={14} />
          </button>
        </header>

        <NewRunForm
          projectRoot={projectRoot}
          defaultScope={defaultScope}
          onCancel={onClose}
          onSuccess={onCreated}
        />
      </div>
    </div>,
    document.body,
  )
}
