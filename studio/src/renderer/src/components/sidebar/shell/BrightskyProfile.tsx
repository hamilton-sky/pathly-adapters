import { useBrightskyStore, BRIGHTSKY_BASE_URL } from '../../../store/brightskyStore'
import { brightskyClient } from '../../../lib/brightskyClient'
import styles from '../Sidebar.module.css'

export function BrightskyProfile(): JSX.Element {
  const authenticated   = useBrightskyStore((s) => s.authenticated)
  const displayName     = useBrightskyStore((s) => s.userDisplayName)
  const email           = useBrightskyStore((s) => s.userEmail)
  const clearAuth       = useBrightskyStore((s) => s.clearAuth)

  if (authenticated && displayName) {
    // ── Logged-in state ────────────────────────────────────────────────
    const initials = displayName
      .split(' ')
      .map((w) => w[0] ?? '')
      .slice(0, 2)
      .join('')
      .toUpperCase()

    return (
      <div className={styles.profileRow}>
        <div className={styles.profileAvatar}>{initials}</div>
        <div className={styles.profileInfo}>
          <span className={styles.profileName}>{displayName}</span>
          {email && <span className={styles.profileEmail}>{email}</span>}
        </div>
        <button
          type="button"
          className={styles.profileLogout}
          title="Sign out of Brightsky"
          onClick={() => {
            clearAuth()
            brightskyClient.disconnect()
          }}
        >
          Sign out
        </button>
      </div>
    )
  }

  // ── Logged-out state ───────────────────────────────────────────────
  return (
    <button
      type="button"
      className={styles.profileSignIn}
      onClick={() => window.pathly?.brightsky?.login(BRIGHTSKY_BASE_URL)}
    >
      <span className={styles.profileSignInDot} />
      Sign in with Brightsky
    </button>
  )
}
