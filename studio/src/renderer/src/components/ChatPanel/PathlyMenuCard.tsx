import { ChevronDown, ChevronUp, X } from 'lucide-react'
import type { PathlyMenu, PathlyMenuItem, PushedMenu } from '../../lib/pathlyContext'
import { useTheme } from '../../useTheme'
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
  const t = useTheme()
  const pushed = isPushedMenu(menu)

  const remainingMs = pushed
    ? Math.max(0, menu.ttl * 1000 - (Date.now() - menu.pushedAt))
    : 0

  return (
    <div
      className={styles.panel}
      style={{ borderBottom: t.border, background: t.bgSurface0 }}
    >
      {/* Header row */}
      <button
        className={styles.headerBtn}
        onClick={onToggle}
        aria-expanded={isOpen}
        style={{ color: t.textSecondary, fontFamily: t.fontFamilyBase }}
      >
        <div className={styles.titleRow}>
          <span className={styles.title} style={{ color: t.textPrimary }}>{menu.title}</span>
          <span className={styles.badge} style={{ color: t.textMuted, borderColor: t.bgSurface1 }}>
            {menu.state}
          </span>
        </div>

        <div className={styles.controls}>
          {onDismiss && (
            <span
              className={styles.dismissBtn}
              role="button"
              aria-label="Dismiss"
              onClick={(e) => { e.stopPropagation(); onDismiss() }}
            >
              <X size={11} />
            </span>
          )}
          {isOpen ? <ChevronUp size={13} style={{ flexShrink: 0 }} /> : <ChevronDown size={13} style={{ flexShrink: 0 }} />}
        </div>
      </button>

      {/* Progress bar — pushed menus only */}
      {pushed && remainingMs > 0 && (
        <div
          className={styles.timerBar}
          style={{ animationDuration: `${remainingMs}ms` }}
          onAnimationEnd={onExpire}
        />
      )}

      {/* Collapsible content */}
      {isOpen && (
        <div className={styles.body}>
          {menu.subtitle ? (
            <p className={styles.subtitle} style={{ color: t.textSecondary }}>{menu.subtitle}</p>
          ) : null}
          <div className={styles.items}>
            {menu.items.length > 0 ? menu.items.map((item) => (
              <button
                key={`${item.label}-${item.command}`}
                className={`${styles.item} ${onSelect ? styles.itemClickable : ''}`}
                onClick={onSelect ? () => onSelect(item) : undefined}
                aria-label={`Run: ${item.label}`}
              >
                <div className={styles.itemTop}>
                  <span className={styles.itemLabel} style={{ color: t.textPrimary }}>{item.label}</span>
                  <code className={styles.itemCommand} style={{ color: t.textMuted }}>{item.command}</code>
                </div>
                <div className={styles.itemDescription} style={{ color: t.textSecondary }}>
                  {item.description}
                </div>
              </button>
            )) : (
              <div className={styles.empty} style={{ color: t.textMuted }}>
                {menu.empty_message}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
