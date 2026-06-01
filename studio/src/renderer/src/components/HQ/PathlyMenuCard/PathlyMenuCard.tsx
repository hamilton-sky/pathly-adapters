import { useEffect, useRef } from 'react'
import { ChevronDown, ChevronUp, X } from 'lucide-react'
import type { PathlyMenu, PathlyMenuItem, PushedMenu } from '../../../lib/pathlyContext'
import { useRunnerStore } from '../../../store/runnerStore'
import { DecisionButton } from './DecisionButton'
import styles from './PathlyMenuCard.module.css'

interface PathlyMenuCardProps {
  menu: PathlyMenu | PushedMenu
  onSelect?: (item: PathlyMenuItem) => void
  onDismiss?: () => void   // pushed menus only — × button
  isOpen?: boolean
  onToggle?: () => void
  onExpire?: () => void    // fired when the CSS timer animation ends
}

function isPushedMenu(m: PathlyMenu | PushedMenu): m is PushedMenu {
  return 'ttl' in m && 'pushedAt' in m
}

export function PathlyMenuCard({
  menu,
  onSelect,
  onDismiss,
  isOpen = true,
  onToggle,
  onExpire,
}: PathlyMenuCardProps): JSX.Element {
  const pushed = isPushedMenu(menu)
  const panelRef = useRef<HTMLDivElement>(null)
  const decisionMenu = useRunnerStore((s) => s.decisionMenu)
  const setDecisionMenu = useRunnerStore((s) => s.setDecisionMenu)
  const setRunnerState = useRunnerStore((s) => s.setRunnerState)

  const remainingMs = pushed
    ? Math.max(0, menu.ttl * 1000 - (Date.now() - menu.pushedAt))
    : 0

  useEffect(() => {
    if (panelRef.current && pushed && remainingMs > 0) {
      panelRef.current.style.setProperty('--timer-ms', `${remainingMs}ms`)
    }
  }, [pushed, remainingMs])

  return (
    <div ref={panelRef} className={styles.panel}>
      {/* Header row */}
      <button
        type="button"
        className={styles.headerBtn}
        onClick={onToggle}
        {...(isOpen ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
      >
        <div className={styles.titleRow}>
          <span className={styles.title}>{menu.title}</span>
          <span className={styles.badge}>
            {menu.state}
          </span>
        </div>

        <div className={styles.controls}>
          {onDismiss && (
            <button
              type="button"
              className={styles.dismissBtn}
              aria-label="Dismiss"
              onClick={(e) => { e.stopPropagation(); onDismiss() }}
            >
              <X size={11} />
            </button>
          )}
          {isOpen ? <ChevronUp size={13} className={styles.flexShrinkZero} /> : <ChevronDown size={13} className={styles.flexShrinkZero} />}
        </div>
      </button>

      {/* Progress bar — pushed menus only */}
      {pushed && remainingMs > 0 && (
        <div className={styles.timerBar} onAnimationEnd={onExpire} />
      )}

      {/* Collapsible content */}
      {isOpen && (
        <div className={styles.body}>
          {menu.subtitle ? (
            <p className={styles.subtitle}>{menu.subtitle}</p>
          ) : null}
          {decisionMenu !== null ? (
            <div className={styles.decisionItems} aria-live="polite">
              {decisionMenu.map((item) => (
                <DecisionButton
                  key={item.id}
                  item={item}
                  onError={(msg) => setRunnerState({ errorMessage: msg })}
                  onDone={() => setDecisionMenu(null)}
                />
              ))}
            </div>
          ) : (
            <div className={styles.items}>
              {menu.items.length > 0 ? menu.items.map((item) => (
                <button
                  type="button"
                  key={`${item.label}-${item.command}`}
                  className={`${styles.item} ${onSelect ? styles.itemClickable : ''}`}
                  onClick={onSelect ? () => onSelect(item) : undefined}
                  aria-label={`Run: ${item.label}`}
                >
                  <div className={styles.itemTop}>
                    <span className={styles.itemLabel}>{item.label}</span>
                    <code className={styles.itemCommand}>{item.command}</code>
                  </div>
                  <div className={styles.itemDescription}>
                    {item.description}
                  </div>
                </button>
              )) : (
                <div className={styles.empty}>
                  {menu.empty_message}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
