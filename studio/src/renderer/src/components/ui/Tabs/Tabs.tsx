import clsx from 'clsx'
import styles from './Tabs.module.css'

interface TabItem {
  id: string
  label: React.ReactNode
  count?: number | string
}

interface TabsProps {
  tabs: TabItem[]
  activeId: string
  onChange?: (id: string) => void
  /** "underline" = in-panel tabs. "pill" = top-level view switch. */
  variant?: 'underline' | 'pill'
  className?: string
}

function Tabs({ tabs, activeId, onChange, variant = 'underline', className }: TabsProps) {
  return (
    <div className={clsx(styles.bar, variant === 'pill' ? styles.pill : styles.underline, className)}>
      {tabs.map((t) => {
        const active = t.id === activeId
        return (
          <button
            key={t.id}
            type="button"
            className={clsx(styles.tab, active && styles.active)}
            onClick={() => onChange?.(t.id)}
            {...(active ? { 'aria-selected': 'true' } : { 'aria-selected': 'false' })}
          >
            {t.label}
            {t.count != null && (
              <span className={clsx(styles.count, active && styles.countActive)}>
                {t.count}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
