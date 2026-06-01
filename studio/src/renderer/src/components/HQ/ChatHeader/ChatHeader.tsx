import { useEffect, useRef, useState } from 'react'
import { X, Zap, SquarePen, History, ChevronDown } from 'lucide-react'
import type { TerminalKind } from '../../../store/chatStore'
import { Tooltip } from '../../ui'
import { TERMINAL_OPTIONS } from '../../../lib/terminalOptions'
import styles from './ChatHeader.module.css'

export interface SessionSummary {
  id: string
  title: string
  messageCount: number
  lastActivity: string
}

interface ChatHeaderProps {
  hasClaudeTab: boolean
  hasCodexTab: boolean
  hasShellTab: boolean
  hasAntigravityTab: boolean
  targetKind: TerminalKind
  onSetTarget: (kind: TerminalKind) => void
  onToggleChat: () => void
  onClearChat: () => void
  sessions?: SessionSummary[]
  onSelectSession?: (id: string) => void
}


export function ChatHeader({ hasClaudeTab, hasCodexTab, hasShellTab, hasAntigravityTab, targetKind, onSetTarget, onToggleChat, onClearChat, sessions = [], onSelectSession }: ChatHeaderProps): JSX.Element {
  const [targetOpen, setTargetOpen] = useState(false)
  const [sessionsOpen, setSessionsOpen] = useState(false)
  const targetRef = useRef<HTMLDivElement>(null)
  const sessionsRef = useRef<HTMLDivElement>(null)

  const activeByKind: Record<TerminalKind, boolean> = {
    claude: hasClaudeTab,
    codex: hasCodexTab,
    shell: hasShellTab,
    antigravity: hasAntigravityTab,
  }

  const current = TERMINAL_OPTIONS.find((o) => o.kind === targetKind) ?? TERMINAL_OPTIONS[0]

  useEffect(() => {
    if (!targetOpen) return
    const handler = (e: MouseEvent): void => {
      if (!targetRef.current?.contains(e.target as Node)) setTargetOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [targetOpen])

  useEffect(() => {
    if (!sessionsOpen) return
    const handler = (e: MouseEvent): void => {
      if (!sessionsRef.current?.contains(e.target as Node)) setSessionsOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [sessionsOpen])

  function formatActivity(iso: string): string {
    const diff = Date.now() - new Date(iso).getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 1) return 'just now'
    if (mins < 60) return `${mins}m ago`
    const hrs = Math.floor(mins / 60)
    if (hrs < 24) return `${hrs}h ago`
    return `${Math.floor(hrs / 24)}d ago`
  }

  return (
    <div className={styles.header}>
      <div className={styles.titleRow}>
        <span className={styles.title}>
          <Zap size={13} /> HQ
        </span>
        <span className={styles.subtitle}>Pipeline Control</span>
      </div>

      {/* Target selector — single dropdown replacing the pill row */}
      <div ref={targetRef} className={styles.targetWrapper}>
        <Tooltip label="Select target terminal" placement="bottom">
          <button
            type="button"
            className={`${styles.targetBtn} ${targetOpen ? styles.targetBtnOpen : ''}`}
            onClick={() => setTargetOpen((v) => !v)}
            aria-label="Select target terminal"
            {...(targetOpen ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
          >
            <span className={styles.targetIcon}>{current.icon(13)}</span>
            <span className={`${styles.dot} ${activeByKind[targetKind] ? styles.dotActive : ''}`} />
            <span className={styles.targetLabel}>{current.label}</span>
            <ChevronDown size={10} />
          </button>
        </Tooltip>

        {targetOpen && (
          <div className={styles.targetDropdown}>
            {TERMINAL_OPTIONS.map((opt) => (
              <button
                key={opt.kind}
                type="button"
                className={`${styles.targetItem} ${targetKind === opt.kind ? styles.targetItemSelected : ''}`}
                onClick={() => { onSetTarget(opt.kind); setTargetOpen(false) }}
                aria-label={`Target ${opt.label}`}
              >
                <span className={styles.targetItemIcon}>{opt.icon(13)}</span>
                <span className={`${styles.dot} ${activeByKind[opt.kind] ? styles.dotActive : ''}`} />
                <span>{opt.label}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* New session */}
      <Tooltip label="New session" placement="bottom">
        <button type="button" className={styles.closeBtn} onClick={onClearChat} aria-label="New session">
          <SquarePen size={13} />
        </button>
      </Tooltip>

      {/* Sessions history dropdown */}
      <div ref={sessionsRef} className={styles.sessionsWrapper}>
        <Tooltip label="Session history" placement="bottom">
          <button
            type="button"
            className={`${styles.closeBtn} ${sessionsOpen ? styles.closeBtnActive : ''}`}
            onClick={() => setSessionsOpen((v) => !v)}
            aria-label="Session history"
            {...(sessionsOpen ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
          >
            <History size={13} />
            {sessions.length > 0 && (
              <span className={`${styles.sessionsBadge} ${styles.sessionsBadgeAccent}`}>
                {sessions.length > 9 ? '9+' : sessions.length}
              </span>
            )}
          </button>
        </Tooltip>

        {sessionsOpen && (
          <div className={styles.sessionsDropdown}>
            <div className={styles.sessionsHeader}>Conversations</div>
            {sessions.length === 0 ? (
              <div className={styles.sessionsEmpty}>
                No sessions yet.
                <br />
                <span className={styles.sessionsEmptyHint}>Connect Brightsky to see history.</span>
              </div>
            ) : (
              <div className={styles.sessionsList}>
                {sessions.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    className={styles.sessionItem}
                    onClick={() => { onSelectSession?.(s.id); setSessionsOpen(false) }}
                  >
                    <span className={styles.sessionTitle}>{s.title}</span>
                    <span className={styles.sessionMeta}>
                      {s.messageCount} msg · {formatActivity(s.lastActivity)}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <Tooltip label="Close chat panel" placement="bottom">
        <button type="button" className={styles.closeBtn} onClick={onToggleChat} aria-label="Close chat panel">
          <X size={14} />
        </button>
      </Tooltip>
    </div>
  )
}
