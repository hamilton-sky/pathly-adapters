import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { useToastStore } from '../store/toastStore'
import styles from './Toaster.module.css'

export function Toaster(): JSX.Element {
  const { toasts, remove } = useToastStore()
  return createPortal(
    <div className={styles.container}>
      {toasts.map((t) => (
        <div key={t.id} className={`${styles.toast} ${styles[t.variant]}`}>
          <span className={styles.message}>{t.message}</span>
          <button className={styles.close} onClick={() => remove(t.id)} aria-label="Dismiss">
            <X size={14} />
          </button>
        </div>
      ))}
    </div>,
    document.body
  )
}
