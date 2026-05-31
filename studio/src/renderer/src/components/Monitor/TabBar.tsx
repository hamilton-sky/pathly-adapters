import React, { useCallback, useEffect, useRef } from 'react'
import type { FlowSession } from '../../types/index'
import { extractTopic, flowTypeLabel, truncate } from './utils'
import styles from './Monitor.module.css'

interface Props {
  sessions: Record<string, FlowSession>
  activeTab: string | null
  onTabSelect: (key: string) => void
}

export function TabBar({ sessions, activeTab, onTabSelect }: Props): JSX.Element {
  const keys = Object.keys(sessions)
  const focusedTabRef = useRef<number>(keys.indexOf(activeTab ?? keys[0]))
  const tablistRef = useRef<HTMLDivElement>(null)

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLButtonElement>, idx: number): void => {
    if (e.key === 'ArrowRight') {
      e.preventDefault()
      const nextIdx = (idx + 1) % keys.length
      onTabSelect(keys[nextIdx])
      focusedTabRef.current = nextIdx
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault()
      const prevIdx = (idx - 1 + keys.length) % keys.length
      onTabSelect(keys[prevIdx])
      focusedTabRef.current = prevIdx
    }
  }, [keys, onTabSelect])

  const visible = keys.slice(0, 4)
  const overflow = keys.slice(4)
  const allSameTopic = keys.length > 0 && keys.every((k) => extractTopic(k) === extractTopic(keys[0]))

  // Set aria-selected imperatively to avoid JSX expression lint false-positive
  useEffect(() => {
    if (!tablistRef.current) return
    tablistRef.current.querySelectorAll<HTMLButtonElement>('[role="tab"][data-key]').forEach((btn) => {
      const isActive = btn.dataset.key === (activeTab ?? visible[0] ?? '')
      btn.setAttribute('aria-selected', String(isActive))
    })
  }, [activeTab, visible])

  return (
    <div className={styles.tabBar}>
      {/* tablist must only contain role="tab" children — overflow button lives outside */}
      <div ref={tablistRef} role="tablist" aria-label="Active flows" className={styles.tabListInner}>
        {visible.map((sessionKey, idx) => {
          const session = sessions[sessionKey]
          const isActive = activeTab === sessionKey || (activeTab === null && idx === 0)
          const label = allSameTopic
            ? flowTypeLabel(session.flowKey)
            : `${flowTypeLabel(session.flowKey)}/${truncate(extractTopic(sessionKey), 10)}`
          return (
            <button
              key={sessionKey}
              data-key={sessionKey}
              type="button"
              role="tab"
              tabIndex={isActive ? 0 : -1}
              onClick={() => onTabSelect(sessionKey)}
              onKeyDown={(e) => handleKeyDown(e, idx)}
              className={`${styles.tab} ${isActive ? styles.tabActive : ''}`}
            >
              {label}
              {session.isRunning && (
                <span className={styles.tabDot} aria-hidden="true">●</span>
              )}
            </button>
          )
        })}
      </div>
      {overflow.length > 0 && (
        <button
          type="button"
          className={styles.tabOverflow}
          onClick={() => { /* overflow dropdown — Post-MVP */ }}
        >
          …
        </button>
      )}
    </div>
  )
}
