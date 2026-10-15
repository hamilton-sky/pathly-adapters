import { useEffect, useRef, type KeyboardEvent, type ReactNode } from 'react'
import type { HqScopeTab } from '../../../../store/hqComposerStore'
import styles from './ScopePopover.module.css'

export interface ScopeTabDef {
  id: HqScopeTab
  label: string
}

interface Props {
  id: string
  tabs: ScopeTabDef[]
  active: HqScopeTab
  onSelect: (tab: HqScopeTab) => void
  /** The one shared token meter, above the tab body. */
  meter: ReactNode
  children: ReactNode
}

/** The composer's one popover: a segmented tab switch (styled like the model
 *  picker's Fast/Deep toggle), the shared meter, then the active tab's body.
 *  A single tab shows as a heading instead of a one-tab tablist. */
export function ScopePopover({ id, tabs, active, onSelect, meter, children }: Props): JSX.Element {
  const ref = useRef<HTMLDivElement>(null)
  const tabRefs = useRef<Partial<Record<HqScopeTab, HTMLButtonElement | null>>>({})

  // Opened from a chip or an answer's "Adjust" link: focus lands in the popover.
  useEffect(() => {
    ref.current?.focus()
  }, [])

  function onTabKey(e: KeyboardEvent<HTMLDivElement>): void {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
    e.preventDefault()
    const i = tabs.findIndex((t) => t.id === active)
    const next = tabs[(i + (e.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length].id
    onSelect(next)
    tabRefs.current[next]?.focus()
  }

  const tabbed = tabs.length > 1
  return (
    <div id={id} ref={ref} tabIndex={-1} className={styles.popover} role="dialog" aria-label="What the next question includes">
      {tabbed ? (
        <div className={styles.tabs} role="tablist" aria-label="Scope" onKeyDown={onTabKey}>
          {tabs.map((t) => (
            <button
              key={t.id}
              ref={(el) => { tabRefs.current[t.id] = el }}
              type="button"
              role="tab"
              id={`${id}-tab-${t.id}`}
              aria-controls={`${id}-panel`}
              tabIndex={t.id === active ? 0 : -1}
              className={styles.tab}
              data-active={t.id === active ? 'true' : 'false'}
              onClick={() => onSelect(t.id)}
              {...(t.id === active ? { 'aria-selected': 'true' } : { 'aria-selected': 'false' })}
            >
              {t.label}
            </button>
          ))}
        </div>
      ) : (
        <div className={styles.heading}>{tabs[0]?.label}</div>
      )}
      {meter}
      <div
        id={`${id}-panel`}
        className={styles.panel}
        {...(tabbed ? { role: 'tabpanel', 'aria-labelledby': `${id}-tab-${active}` } : {})}
      >
        {children}
      </div>
    </div>
  )
}
