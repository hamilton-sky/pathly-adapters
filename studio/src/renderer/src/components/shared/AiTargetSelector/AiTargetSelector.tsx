import { useState, useRef, useEffect } from 'react'
import { ChevronDown } from 'lucide-react'
import { type AiSelection } from '../../../services/aiRouter'
import { buildGroups, encode, decode, labelForValue } from './options'
import s from './AiTargetSelector.module.css'

// Custom dropdown (button trigger + panel) emitting an AiSelection — a local model
// or a CLI engine. Replaces the old native <select>; matches Studio's house dropdown
// style (HQ/ModelSelector): outside-click + Escape to close, chevron, grouped
// Models / CLI-Engines headers, greyed-out noHeadless engines with their reason, and
// an optional Off row. Public props/value/onChange API and the AI_SELECTION_OFF
// encoding are unchanged so ArtifactsView + Settings keep working. Lives in shared/.

interface Props {
  value: AiSelection | null
  onChange: (sel: AiSelection) => void
  /** When true, adds an "Off" row that emits AI_SELECTION_OFF (consumers skip the run). */
  allowOff?: boolean
  id?: string
  ariaLabel?: string
  /** Disable the whole control (e.g. while a run is in flight). */
  disabled?: boolean
}

export function AiTargetSelector({
  value,
  onChange,
  allowOff = false,
  id,
  ariaLabel = 'AI target',
  disabled = false,
}: Props): JSX.Element {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const groups = buildGroups(allowOff)
  const current = encode(value)
  const triggerLabel = current === '' ? 'Select AI target…' : labelForValue(current, groups)

  // Close on outside click or Escape (mirrors ModelSelector).
  useEffect(() => {
    if (!open) return
    function onMouseDown(e: MouseEvent): void {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    function onKeyDown(e: KeyboardEvent): void {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onMouseDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onMouseDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  function pick(optValue: string): void {
    setOpen(false)
    onChange(decode(optValue))
  }

  return (
    <div className={s.wrap} ref={ref} data-state={disabled ? 'loading' : 'ready'}>
      <button
        type="button"
        id={id}
        className={s.trigger}
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
      >
        <span className={s.triggerLabel} data-placeholder={current === '' ? '' : undefined}>
          {triggerLabel}
        </span>
        <ChevronDown size={13} className={open ? s.chevronOpen : s.chevron} />
      </button>

      {open && (
        <div className={s.panel} role="listbox" aria-label={ariaLabel}>
          {groups.map((group, gi) => (
            <div key={group.heading || `off-${gi}`} className={s.group}>
              {group.heading && <div className={s.groupHeading}>{group.heading}</div>}
              {group.options.map((opt) => {
                const isDisabled = Boolean(opt.disabledReason)
                return (
                  <button
                    key={opt.value}
                    type="button"
                    role="option"
                    {...(opt.value === current
                      ? { 'aria-selected': 'true' }
                      : { 'aria-selected': 'false' })}
                    className={s.option}
                    data-selected={opt.value === current ? '' : undefined}
                    disabled={isDisabled}
                    title={opt.disabledReason}
                    onClick={() => !isDisabled && pick(opt.value)}
                  >
                    <span className={s.optionLabel}>{opt.label}</span>
                    {opt.disabledReason && (
                      <span className={s.optionReason}>{opt.disabledReason}</span>
                    )}
                  </button>
                )
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
