import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode, type KeyboardEvent } from 'react'
import { createPortal } from 'react-dom'
import { ChevronDown, Check } from 'lucide-react'
import s from './BoardSelect.module.css'

export interface BoardSelectOption {
  value: string
  label: string
  /** Optional secondary line shown under the label (e.g. model · role, or a blurb). */
  hint?: string
}

interface Props {
  value: string
  options: BoardSelectOption[]
  onChange: (value: string) => void
  id?: string
  ariaLabel?: string
  /** Optional icon shown at the left of the trigger. */
  leadingIcon?: ReactNode
  /** Text shown in the trigger when no option matches the current value. */
  placeholder?: string
  /** Extra class on the trigger button — lets a caller flatten it into a grouped control. */
  triggerClassName?: string
}

interface Pos { top: number; left: number; width: number; up: boolean; maxH: number }

/**
 * Custom dropdown matching the ProjectSelector portaled-menu look — used inside the
 * board's run modal/popovers where a native <select> can't render two-line rows or
 * match the dark theme. Keyboard accessible: ArrowUp/Down, Home/End, Enter/Space,
 * Escape, and single-key typeahead. The menu portals to <body> so an overflow:auto
 * modal body can't clip it; it closes on outside-click, scroll, and resize.
 */
export function BoardSelect({ value, options, onChange, id, ariaLabel, leadingIcon, placeholder, triggerClassName }: Props): JSX.Element {
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState<Pos | null>(null)
  const [activeIdx, setActiveIdx] = useState(0)
  // Scroll affordance: whether the list overflows and which edges are reached.
  const [scroll, setScroll] = useState({ overflow: false, top: true, bottom: true })
  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const typeahead = useRef<{ str: string; at: number }>({ str: '', at: 0 })

  const current = options.find((o) => o.value === value)

  // Recompute the scroll affordance (drives the fade gradients + count header).
  const updateScroll = useCallback((): void => {
    const el = scrollRef.current
    if (!el) return
    const overflow = el.scrollHeight - el.clientHeight > 1
    const atTop = el.scrollTop <= 1
    const atBottom = el.scrollTop >= el.scrollHeight - el.clientHeight - 1
    setScroll((prev) =>
      prev.overflow === overflow && prev.top === atTop && prev.bottom === atBottom
        ? prev
        : { overflow, top: atTop, bottom: atBottom })
  }, [])

  function place(): void {
    const r = triggerRef.current?.getBoundingClientRect()
    if (!r) return
    const margin = 8
    const spaceBelow = window.innerHeight - r.bottom - margin
    const spaceAbove = r.top - margin
    const up = spaceBelow < 200 && spaceAbove > spaceBelow
    // Cap the scroll area to the space available (minus ~30px so the optional count
    // header still fits) so the menu never overflows the viewport — when the list is
    // taller than that, the scroll area scrolls internally.
    const maxH = Math.max(140, Math.min(264, (up ? spaceAbove : spaceBelow) - 30))
    setPos({ top: up ? r.top - 4 : r.bottom + 4, left: r.left, width: r.width, up, maxH })
  }

  function openMenu(): void {
    place()
    const idx = options.findIndex((o) => o.value === value)
    setActiveIdx(idx >= 0 ? idx : 0)
    setOpen(true)
  }
  function close(): void { setOpen(false) }
  function choose(v: string): void { onChange(v); close(); triggerRef.current?.focus() }

  // On open: focus the menu (so arrow keys work), measure overflow, and watch for
  // size changes (e.g. the count header appearing) to keep the fades accurate.
  useLayoutEffect(() => {
    if (!open) return
    menuRef.current?.focus()
    updateScroll()
    const el = scrollRef.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(() => updateScroll())
    ro.observe(el)
    return () => ro.disconnect()
  }, [open, updateScroll])

  // Keep the active row in view as the user arrows through.
  useEffect(() => {
    if (!open) return
    menuRef.current?.querySelector<HTMLElement>(`[data-idx="${activeIdx}"]`)?.scrollIntoView({ block: 'nearest' })
  }, [activeIdx, open])

  // Close on outside click, scroll (the menu is anchored, not reflowed), or resize.
  useEffect(() => {
    if (!open) return
    function onOutside(e: MouseEvent): void {
      const t = e.target as Node
      if (menuRef.current?.contains(t) || triggerRef.current?.contains(t)) return
      close()
    }
    function onScroll(e: Event): void {
      // Scrolling WITHIN the menu must NOT close it — only an outside scroll
      // (the modal body, the page) moves the anchor and should dismiss it.
      const t = e.target as Node
      if (menuRef.current && menuRef.current.contains(t)) return
      close()
    }
    function onResize(): void { close() }
    document.addEventListener('mousedown', onOutside)
    window.addEventListener('resize', onResize)
    window.addEventListener('scroll', onScroll, true)
    return () => {
      document.removeEventListener('mousedown', onOutside)
      window.removeEventListener('resize', onResize)
      window.removeEventListener('scroll', onScroll, true)
    }
  }, [open])

  function onTriggerKey(e: KeyboardEvent): void {
    if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openMenu() }
  }

  function onMenuKey(e: KeyboardEvent): void {
    if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(); triggerRef.current?.focus(); return }
    if (e.key === 'ArrowDown') { e.preventDefault(); setActiveIdx((i) => Math.min(options.length - 1, i + 1)); return }
    if (e.key === 'ArrowUp') { e.preventDefault(); setActiveIdx((i) => Math.max(0, i - 1)); return }
    if (e.key === 'Home') { e.preventDefault(); setActiveIdx(0); return }
    if (e.key === 'End') { e.preventDefault(); setActiveIdx(options.length - 1); return }
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); const o = options[activeIdx]; if (o) choose(o.value); return }
    if (e.key === 'Tab') { close(); return }
    if (e.key.length === 1 && !e.metaKey && !e.ctrlKey && !e.altKey) {
      const now = Date.now()
      const ta = typeahead.current
      ta.str = now - ta.at > 700 ? e.key : ta.str + e.key
      ta.at = now
      const hit = options.findIndex((o) => o.label.toLowerCase().startsWith(ta.str.toLowerCase()))
      if (hit >= 0) setActiveIdx(hit)
    }
  }

  return (
    <div className={s.wrap}>
      <button
        ref={triggerRef}
        type="button"
        id={id}
        className={triggerClassName ? `${s.trigger} ${triggerClassName}` : s.trigger}
        aria-haspopup="listbox"
        {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
        {...(ariaLabel ? { 'aria-label': ariaLabel } : {})}
        onClick={() => (open ? close() : openMenu())}
        onKeyDown={onTriggerKey}
      >
        {leadingIcon && <span className={s.lead}>{leadingIcon}</span>}
        <span className={`${s.triggerLabel} ${current ? '' : s.placeholder}`}>
          {current?.label ?? placeholder ?? '—'}
        </span>
        <ChevronDown size={13} className={s.chev} />
      </button>

      {open && pos && createPortal(
        <div
          ref={menuRef}
          className={s.menu}
          role="listbox"
          tabIndex={-1}
          data-board-select-menu=""
          data-dir={pos.up ? 'up' : 'down'}
          {...(ariaLabel ? { 'aria-label': ariaLabel } : {})}
          style={{ top: pos.top, left: pos.left, width: pos.width }}
          onKeyDown={onMenuKey}
        >
          {scroll.overflow && (
            <div className={s.menuHead}>{options.length} options</div>
          )}
          <div className={s.scrollWrap}>
            <div className={s.scroll} ref={scrollRef} onScroll={updateScroll} style={{ maxHeight: pos.maxH }}>
              {options.map((o, i) => {
                const selected = o.value === value
                return (
                  <button
                    key={o.value || `__${i}`}
                    type="button"
                    role="option"
                    data-idx={i}
                    {...(selected ? { 'aria-selected': 'true' } : { 'aria-selected': 'false' })}
                    {...(i === activeIdx ? { 'data-active': 'true' } : {})}
                    {...(selected ? { 'data-selected': 'true' } : {})}
                    className={s.item}
                    onMouseEnter={() => setActiveIdx(i)}
                    onClick={() => choose(o.value)}
                  >
                    <span className={s.check}>{selected && <Check size={13} />}</span>
                    <span className={s.itemBody}>
                      <span className={s.itemLabel}>{o.label}</span>
                      {o.hint && <span className={s.itemHint}>{o.hint}</span>}
                    </span>
                  </button>
                )
              })}
            </div>
            {scroll.overflow && !scroll.top && <div className={s.fadeTop} aria-hidden="true" />}
            {scroll.overflow && !scroll.bottom && <div className={s.fadeBottom} aria-hidden="true" />}
          </div>
        </div>,
        document.body,
      )}
    </div>
  )
}
