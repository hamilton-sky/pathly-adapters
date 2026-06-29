import { useState, useEffect, useRef, useLayoutEffect } from 'react'
import { createPortal } from 'react-dom'
import { ChevronDown, Check } from 'lucide-react'
import styles from './GoalSelect.module.css'

export interface GoalSelectOption {
  value: string
  label: string
  hint?: string
  disabled?: boolean
}

interface Props {
  value: string
  options: GoalSelectOption[]
  onChange: (v: string) => void
  ariaLabel?: string
  menuLabel?: string
  /** Disables the entire trigger (e.g. while a run is active). */
  disabled?: boolean
  /** Fixed trigger width in px — prevents layout shift when the selected label changes. */
  minWidth?: number
}

interface MenuPos { top: number; left: number; minWidth: number }

// Compact portaled custom dropdown for the goal card controls row.
// Portals to <body> so the card's overflow never clips the menu.
// Matches CliSelect's trigger style; opens downward.
export function GoalSelect({ value, options, onChange, ariaLabel, menuLabel, disabled, minWidth }: Props): JSX.Element {
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState<MenuPos | null>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  function place(): void {
    const r = triggerRef.current?.getBoundingClientRect()
    if (!r) return
    setPos({ top: r.bottom + 4, left: r.left, minWidth: r.width })
  }

  function openMenu(): void {
    place()
    setOpen(true)
  }

  useLayoutEffect(() => {
    if (open) menuRef.current?.focus()
  }, [open])

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node
      if (menuRef.current?.contains(t) || triggerRef.current?.contains(t)) return
      setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    const onClose = () => setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    window.addEventListener('scroll', onClose, true)
    window.addEventListener('resize', onClose)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
      window.removeEventListener('scroll', onClose, true)
      window.removeEventListener('resize', onClose)
    }
  }, [open])

  const current = options.find((o) => o.value === value) ?? options[0]

  return (
    <div className={styles.wrap}>
      <button
        ref={triggerRef}
        type="button"
        className={styles.trigger}
        disabled={disabled}
        {...(minWidth ? { style: { minWidth: `${minWidth}px` } as React.CSSProperties } : {})}
        aria-haspopup="menu"
        {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
        {...(ariaLabel ? { 'aria-label': ariaLabel } : {})}
        onClick={() => (open ? setOpen(false) : openMenu())}
      >
        <span className={styles.label}>{current?.label ?? '—'}</span>
        <ChevronDown size={11} />
      </button>

      {open && pos && createPortal(
        <div
          ref={menuRef}
          className={styles.menu}
          role="menu"
          tabIndex={-1}
          style={{ top: pos.top, left: pos.left, minWidth: pos.minWidth } as React.CSSProperties}
        >
          {menuLabel && <div className={styles.menuHead}>{menuLabel}</div>}
          {options.map((o) => (
            <button
              key={o.value}
              type="button"
              role="menuitemradio"
              disabled={o.disabled}
              title={o.hint}
              {...(value === o.value ? { 'aria-checked': 'true' } : { 'aria-checked': 'false' })}
              className={styles.item}
              onClick={() => { if (!o.disabled) { onChange(o.value); setOpen(false) } }}
            >
              <span className={styles.check}>{value === o.value ? <Check size={13} /> : null}</span>
              <span className={styles.itemLabel}>{o.label}</span>
              {o.hint && <span className={styles.itemHint}>{o.hint}</span>}
            </button>
          ))}
        </div>,
        document.body,
      )}
    </div>
  )
}
