import { Sun, Moon } from 'lucide-react'
import { useStore } from '../../../store'
import { isLightPalette } from '../../../theme'
import styles from './AppHeader.module.css'

interface AppHeaderProps {
  activeTab: 'projects' | 'getting-started' | 'settings'
  onTabChange: (tab: 'projects' | 'getting-started' | 'settings') => void
}

const TAB_LABELS: Record<'projects' | 'getting-started' | 'settings', string> = {
  projects: 'Projects',
  'getting-started': 'Getting Started',
  settings: 'Settings',
}

export function AppHeader({ activeTab, onTabChange }: AppHeaderProps): JSX.Element {
  const { theme, setTheme, preferredDark, preferredLight } = useStore()

  return (
    <div className={styles.header} style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}>
      <div className={styles.tabs}>
        {(['projects', 'getting-started', 'settings'] as const).map((tab) => (
          <button
            type="button"
            key={tab}
            data-testid={`homescreen-tab-${tab}`}
            className={`${styles.tab} ${activeTab === tab ? styles.active : ''}`}
            onClick={() => onTabChange(tab)}
          >
            {TAB_LABELS[tab]}
          </button>
        ))}
      </div>

      <div className={styles.themeToggleWrap}>
        <button
          type="button"
          data-testid="home-theme-toggle"
          className={styles.themeBtn}
          onClick={() => setTheme(isLightPalette(theme) ? preferredDark : preferredLight)}
          title={isLightPalette(theme) ? 'Switch to dark mode' : 'Switch to light mode'}
          aria-label={isLightPalette(theme) ? 'Switch to dark mode' : 'Switch to light mode'}
        >
          {isLightPalette(theme) ? <Moon size={14} /> : <Sun size={14} />}
        </button>
      </div>
    </div>
  )
}
