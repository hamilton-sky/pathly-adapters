import React from 'react'
import { useStore } from '../../store'
import { useInjectCSS, truncate } from './utils'
import { StatePill } from '../ui/StatePill/StatePill'
import styles from './Monitor.module.css'

const LIVE_BADGE_CSS = `
@keyframes pathly-live-breathe {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.pathly-live-dot { animation: none; }
@media (prefers-reduced-motion: no-preference) {
  .pathly-live-dot { animation: pathly-live-breathe 2s ease-in-out infinite; }
}
`

interface Props {
  effectiveTopic: string | null
}

export function HeaderBar({ effectiveTopic }: Props): JSX.Element {
  const { fsmState, monitorSource } = useStore()
  useInjectCSS(LIVE_BADGE_CSS)

  const currentState = fsmState?.current as string | undefined

  const flow = fsmState?.flow as string | undefined
  const topic = effectiveTopic
    ? truncate(effectiveTopic, 32)
    : fsmState?.feature ? truncate(fsmState.feature as string, 32) : '—'
  const conv = fsmState?.conv != null
    ? String(fsmState.conv)
    : fsmState?.current_conversation != null
      ? String(fsmState.current_conversation)
      : null

  const metaParts: string[] = []
  if (flow) metaParts.push(flow)
  if (conv) metaParts.push(`conv ${conv}`)

  const badgeDotClass = monitorSource === 'sse' ? 'pathly-live-dot' : undefined
  const badgeDot = monitorSource == null ? '○' : '●'
  const badgeLabel = monitorSource === 'sse' ? 'live'
    : monitorSource === 'chokidar' ? 'syncing' : 'offline'
  const badgeAriaLabel = monitorSource === 'sse' ? 'Live SSE connection'
    : monitorSource === 'chokidar' ? 'Syncing via file watcher' : 'Not connected'
  const badgeColorClass = monitorSource === 'sse' ? styles.badgeLive
    : monitorSource === 'chokidar' ? styles.badgeSyncing
    : styles.badgeOffline

  return (
    <div className={styles.headerRoot}>
      <div className={styles.headerTopRow}>
        <span className={styles.headerTitle}>{topic}</span>
        {currentState && currentState !== 'IDLE' && (
          <StatePill state={currentState as Parameters<typeof StatePill>[0]['state']} className={styles.headerStatePill} />
        )}
        <span
          role="status"
          aria-live="polite"
          aria-atomic="true"
          aria-label={badgeAriaLabel}
          className={`${styles.headerBadge} ${badgeColorClass}`}
        >
          <span className={badgeDotClass} aria-hidden="true">{badgeDot}</span>
          <span aria-hidden="true">{badgeLabel}</span>
        </span>
      </div>
    </div>
  )
}
