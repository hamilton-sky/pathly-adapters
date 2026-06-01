import { BRIGHTSKY_BASE_URL } from '../../../store/brightskyStore'
import { brightskyClient } from '../../../lib/brightskyClient'
import styles from './ModelSelector.module.css'

interface BrightskyCardProps {
  isSelected: boolean
  authenticated: boolean
  connected: boolean
  authError: string | null
  onSelect: () => void
  onConnect: () => void
  onDisconnect: () => void
}

export function BrightskyCard({
  isSelected,
  authenticated,
  connected,
  authError,
  onSelect,
  onConnect,
  onDisconnect,
}: BrightskyCardProps): JSX.Element {
  return (
    <div
      className={`${styles.card} ${isSelected ? styles.cardSelected : ''}`}
      onClick={onSelect}
    >
      <div className={styles.cardHeader}>
        <span className={styles.cardName}>Brightsky</span>
        <div className={styles.badges}>
          {isSelected && (
            <span className={styles.badgeSelected}>Selected</span>
          )}
        </div>
      </div>
      <p className={styles.cardDesc}>Cloud AI backend — streams responses via WebSocket.</p>

      <div className={styles.statusRow}>
        <span className={`${styles.statusDot} ${authenticated ? styles.statusDotConnected : styles.statusDotDisconnected}`} />
        <span className={styles.statusText}>{connected ? 'Connected' : 'Disconnected'}</span>
      </div>

      {!authenticated ? (
        <button
          type="button"
          className={styles.cacheBtn}
          onClick={(e) => {
            e.stopPropagation()
            window.pathly?.brightsky?.login(BRIGHTSKY_BASE_URL)
            onConnect()
          }}
        >
          Connect with Google
        </button>
      ) : (
        <button
          type="button"
          className={`${styles.cacheBtn} ${styles.cacheBtnOn}`}
          onClick={(e) => {
            e.stopPropagation()
            onDisconnect()
            brightskyClient.disconnect()
          }}
        >
          Disconnect
        </button>
      )}

      {authError && (
        <div className={styles.authError}>{authError}</div>
      )}
    </div>
  )
}
