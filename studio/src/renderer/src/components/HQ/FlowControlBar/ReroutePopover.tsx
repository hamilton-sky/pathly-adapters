import { useEffect, useRef, useState } from 'react'
import { ADAPTERS } from '../../../lib/adapters.gen'
import { useRunnerStore } from '../../../store/runnerStore'
import styles from './ReroutePopover.module.css'
import { apiFetch } from '../../../lib/config'

interface ReroutePopoverProps {
  onClose: () => void
  onError: (msg: string) => void
}

export function ReroutePopover({ onClose, onError }: ReroutePopoverProps): JSX.Element {
  const currentAdapter = useRunnerStore((s) => s.adapter)
  const adapterKeys = Object.keys(ADAPTERS)
  const [selected, setSelected] = useState<string>(currentAdapter ?? adapterKeys[0] ?? 'claude')
  const popoverRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent): void {
      if (e.key === 'Escape') onClose()
    }
    function handleMouseDown(e: MouseEvent): void {
      if (!popoverRef.current?.contains(e.target as Node)) onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    document.addEventListener('mousedown', handleMouseDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.removeEventListener('mousedown', handleMouseDown)
    }
  }, [onClose])

  async function handleReroute(): Promise<void> {
    const { topic } = useRunnerStore.getState()
    try {
      const res = await apiFetch('/runner/reroute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic, adapter: selected }),
      })
      if (!res.ok) onError(`reroute failed: ${res.status}`)
    } catch {
      onError('reroute failed: network error')
    }
    onClose()
  }

  return (
    <div ref={popoverRef} className={styles.popover} role="dialog" aria-label="Reroute to adapter">
      <div className={styles.title}>Reroute to adapter</div>
      <select
        className={styles.select}
        value={selected}
        onChange={(e) => setSelected(e.target.value)}
        aria-label="Select adapter"
      >
        {adapterKeys.map((key) => (
          <option key={key} value={key}>
            {key}
          </option>
        ))}
      </select>
      <div className={styles.chips} aria-hidden="true">
        {adapterKeys.map((key) => (
          <span
            key={key}
            className={`${styles.chip} ${selected === key ? styles.chipActive : ''}`}
            ref={(el) => { if (el) el.style.setProperty('--chip-color', ADAPTERS[key].color) }}
          />
        ))}
      </div>
      <div className={styles.actions}>
        <button type="button" className={styles.rerouteBtn} onClick={() => { void handleReroute() }} aria-label="Confirm reroute">
          Reroute
        </button>
        <button type="button" className={styles.cancelBtn} onClick={onClose} aria-label="Cancel reroute">
          Cancel
        </button>
      </div>
    </div>
  )
}
