import { useEffect, useRef, useState } from 'react'
import { ADAPTERS } from '../../../../lib/adapters.gen'
import s from './RerouteMenu.module.css'

interface Props {
  onConfirm: (adapter: string) => void
  onCancel: () => void
}

// Inline adapter picker for RunControls' Reroute action — mirrors HQ/FlowControlBar's
// ReroutePopover (same ADAPTERS source + outside-click/Escape dismiss), but run_id-addressed:
// it only collects the chosen adapter and hands it back to the caller, which owns the actual
// POST /runs/<id>/reroute call (RunControls' useRunControls hook).
export function RerouteMenu({ onConfirm, onCancel }: Props): JSX.Element {
  const adapterKeys = Object.keys(ADAPTERS)
  const [selected, setSelected] = useState<string>(adapterKeys[0] ?? 'claude')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent): void {
      if (e.key === 'Escape') onCancel()
    }
    function onMouseDown(e: MouseEvent): void {
      if (!ref.current?.contains(e.target as Node)) onCancel()
    }
    document.addEventListener('keydown', onKeyDown)
    document.addEventListener('mousedown', onMouseDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.removeEventListener('mousedown', onMouseDown)
    }
  }, [onCancel])

  return (
    <div ref={ref} className={s.menu} role="dialog" aria-label="Reroute to adapter">
      <select
        className={s.select}
        value={selected}
        onChange={(e) => setSelected(e.target.value)}
        aria-label="Select adapter"
      >
        {adapterKeys.map((key) => (
          <option key={key} value={key}>
            {ADAPTERS[key].label}
          </option>
        ))}
      </select>
      <div className={s.actions}>
        <button type="button" className={s.confirm} onClick={() => onConfirm(selected)}>
          Go
        </button>
        <button type="button" className={s.cancel} onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  )
}
