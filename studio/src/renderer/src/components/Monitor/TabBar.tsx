import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { FlowSession } from '../../types/index'
import { extractTopic, flowTypeLabel, truncate } from './utils'
import styles from './Monitor.module.css'

const PAGE_SIZE = 3

interface Props {
  sessions: Record<string, FlowSession>
  activeTab: string | null
  onTabSelect: (key: string) => void
}

export function TabBar({ sessions, activeTab, onTabSelect }: Props): JSX.Element {
  const keys = useMemo(() => Object.keys(sessions), [sessions])
  const [page, setPage] = useState(0)
  const totalPages = Math.ceil(keys.length / PAGE_SIZE)
  const tablistRef = useRef<HTMLDivElement>(null)

  // When active tab changes, jump to its page
  useEffect(() => {
    if (activeTab == null) return
    const idx = keys.indexOf(activeTab)
    if (idx < 0) return
    setPage(Math.floor(idx / PAGE_SIZE))
  }, [activeTab, keys])

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLButtonElement>, globalIdx: number): void => {
    if (e.key === 'ArrowRight') {
      e.preventDefault()
      const nextIdx = (globalIdx + 1) % keys.length
      onTabSelect(keys[nextIdx])
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault()
      const prevIdx = (globalIdx - 1 + keys.length) % keys.length
      onTabSelect(keys[prevIdx])
    }
  }, [keys, onTabSelect])

  const visible = keys.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
  const allSameTopic = keys.length > 0 && keys.every((k) => extractTopic(k) === extractTopic(keys[0]))
  const rangeStart = page * PAGE_SIZE + 1
  const rangeEnd = Math.min((page + 1) * PAGE_SIZE, keys.length)

  useEffect(() => {
    if (!tablistRef.current) return
    tablistRef.current.querySelectorAll<HTMLButtonElement>('[role="tab"][data-key]').forEach((btn) => {
      const isActive = btn.dataset.key === (activeTab ?? visible[0] ?? '')
      btn.setAttribute('aria-selected', String(isActive))
    })
  }, [activeTab, visible])

  return (
    <div className={styles.tabBar}>
      {totalPages > 1 && (
        <button
          type="button"
          className={styles.tabNavBtn}
          onClick={() => setPage((p) => Math.max(0, p - 1))}
          {...(page === 0 ? { disabled: true } : {})}
          aria-label="Previous tabs"
        >
          ‹
        </button>
      )}
      <div ref={tablistRef} role="tablist" aria-label="Active flows" className={styles.tabListInner}>
        {visible.map((sessionKey, idx) => {
          const session = sessions[sessionKey]
          const globalIdx = page * PAGE_SIZE + idx
          const isActive = activeTab === sessionKey || (activeTab === null && globalIdx === 0)
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
              onKeyDown={(e) => handleKeyDown(e, globalIdx)}
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
      {totalPages > 1 && (
        <>
          <span className={styles.tabCounter} aria-label={`Showing tabs ${rangeStart} to ${rangeEnd} of ${keys.length}`}>
            {rangeStart}–{rangeEnd} / {keys.length}
          </span>
          <button
            type="button"
            className={styles.tabNavBtn}
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            {...(page === totalPages - 1 ? { disabled: true } : {})}
            aria-label="Next tabs"
          >
            ›
          </button>
        </>
      )}
    </div>
  )
}
