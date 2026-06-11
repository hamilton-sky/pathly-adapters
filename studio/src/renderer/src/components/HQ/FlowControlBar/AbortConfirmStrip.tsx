import { useRunnerStore } from '../../../store/runnerStore'
import styles from './AbortConfirmStrip.module.css'
import { apiFetch } from '../../../lib/config'

interface AbortConfirmStripProps {
  onDone: () => void
  onCancel: () => void
  onError: (msg: string) => void
}

export function AbortConfirmStrip({ onDone, onCancel, onError }: AbortConfirmStripProps): JSX.Element {
  async function handleConfirm(): Promise<void> {
    const { topic } = useRunnerStore.getState()
    try {
      const res = await apiFetch('/runner/abort', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic }),
      })
      if (!res.ok) {
        onError(`abort failed: ${res.status}`)
      }
    } catch {
      onError('abort failed: network error')
    }
    onDone()
  }

  return (
    <div className={styles.strip} role="alert">
      <span className={styles.label}>Abort the current run?</span>
      <div className={styles.actions}>
        <button type="button" className={styles.confirmBtn} onClick={() => { void handleConfirm() }} aria-label="Confirm abort">
          Confirm abort
        </button>
        <button type="button" className={styles.cancelBtn} onClick={onCancel} aria-label="Cancel abort">
          Cancel
        </button>
      </div>
    </div>
  )
}
