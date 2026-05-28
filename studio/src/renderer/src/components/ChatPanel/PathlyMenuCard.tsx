import type { PathlyMenu } from '../../lib/pathlyContext'
import { useTheme } from '../../useTheme'
import styles from './PathlyMenuCard.module.css'

interface PathlyMenuCardProps {
  menu: PathlyMenu
}

export function PathlyMenuCard({ menu }: PathlyMenuCardProps): JSX.Element {
  const t = useTheme()

  return (
    <section className={styles.card} style={{ background: t.bgSurface0, border: t.border }}>
      <header className={styles.header}>
        <div className={styles.titleRow}>
          <span className={styles.title} style={{ color: t.textPrimary }}>{menu.title}</span>
          <span className={styles.badge} style={{ color: t.textMuted, borderColor: t.bgSurface1 }}>
            {menu.state}
          </span>
        </div>
        {menu.subtitle ? (
          <p className={styles.subtitle} style={{ color: t.textSecondary }}>{menu.subtitle}</p>
        ) : null}
      </header>

      <div className={styles.items}>
        {menu.items.length > 0 ? menu.items.map((item) => (
          <div key={`${item.label}-${item.command}`} className={styles.item}>
            <div className={styles.itemTop}>
              <span className={styles.itemLabel} style={{ color: t.textPrimary }}>{item.label}</span>
              <code className={styles.itemCommand} style={{ color: t.textMuted }}>{item.command}</code>
            </div>
            <div className={styles.itemDescription} style={{ color: t.textSecondary }}>
              {item.description}
            </div>
          </div>
        )) : (
          <div className={styles.empty} style={{ color: t.textMuted }}>
            {menu.empty_message}
          </div>
        )}
      </div>
    </section>
  )
}
