import { useEffect, useRef, useState } from 'react'
import { X, Zap, SquarePen, History } from 'lucide-react'
import type { TerminalKind } from '../../store/chatStore'
import { Tooltip } from '../ui'
import { ClaudeIcon, CodexIcon, ShellIcon } from '../Terminal/BrandIcons'
import { useTheme } from '../../useTheme'
import styles from './ConductorHeader.module.css'

export interface SessionSummary {
  id: string
  title: string
  messageCount: number
  lastActivity: string
}

interface ConductorHeaderProps {
  hasClaudeTab: boolean
  hasCodexTab: boolean
  hasShellTab: boolean
  targetKind: TerminalKind
  onSetTarget: (kind: TerminalKind) => void
  onToggleChat: () => void
  onClearChat: () => void
  sessions?: SessionSummary[]
  onSelectSession?: (id: string) => void
}

export function ConductorHeader({ hasClaudeTab, hasCodexTab, hasShellTab, targetKind, onSetTarget, onToggleChat, onClearChat, sessions = [], onSelectSession }: ConductorHeaderProps): JSX.Element {
  const t = useTheme()
  const headerRef = useRef<HTMLDivElement>(null)
  const [compact, setCompact] = useState(false)
  const [sessionsOpen, setSessionsOpen] = useState(false)
  const sessionsRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = headerRef.current
    if (!el) return
    const update = (): void => setCompact(el.getBoundingClientRect().width < 360)
    update()
    if (typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    if (!sessionsOpen) return
    const handler = (e: MouseEvent): void => {
      if (!sessionsRef.current?.contains(e.target as Node)) setSessionsOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [sessionsOpen])

  const targetPills: Array<{ kind: TerminalKind; label: string; icon: JSX.Element; active: boolean }> = [
    { kind: 'claude', label: 'claude', icon: <ClaudeIcon size={14} />, active: hasClaudeTab },
    { kind: 'codex', label: 'codex', icon: <CodexIcon size={14} />, active: hasCodexTab },
    { kind: 'shell', label: 'shell', icon: <ShellIcon size={14} />, active: hasShellTab },
  ]

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
    <div ref={headerRef} className={styles.header}>
      <div className={styles.titleRow}>
        <span className={styles.title}>
          <Zap size={13} /> HQ
        </span>
      </div>

      <div className={styles.pills}>
        {targetPills.map((pill) => (
          <Tooltip key={pill.kind} label={`Focus ${pill.label} terminal`} placement="bottom">
            <button
              className={`${styles.pill} ${targetKind === pill.kind ? styles.pillSelected : ''} ${compact ? styles.pillCompact : ''}`}
              onClick={() => onSetTarget(pill.kind)}
              aria-label={`Focus ${pill.label} terminal`}
              title={compact ? `Focus ${pill.label}` : undefined}
            >
              <span className={styles.pillIcon}>{pill.icon}</span>
              <span className={`${styles.dot} ${pill.active ? styles.dotActive : ''}`} />
              {!compact && pill.label}
            </button>
          </Tooltip>
        ))}
      </div>

      {/* New session */}
      <Tooltip label="New session" placement="bottom">
        <button className={styles.closeBtn} onClick={onClearChat} aria-label="New session">
          <SquarePen size={13} />
        </button>
      </Tooltip>

      {/* Sessions history dropdown */}
      <div ref={sessionsRef} className={styles.sessionsWrapper}>
        <Tooltip label="Session history" placement="bottom">
          <button
            className={`${styles.closeBtn} ${sessionsOpen ? styles.closeBtnActive : ''}`}
            onClick={() => setSessionsOpen((v) => !v)}
            aria-label="Session history"
          >
            <History size={13} />
            {sessions.length > 0 && (
              <span className={styles.sessionsBadge} style={{ background: t.accent }}>
                {sessions.length > 9 ? '9+' : sessions.length}
              </span>
            )}
          </button>
        </Tooltip>

        {sessionsOpen && (
          <div className={styles.sessionsDropdown} style={{ background: t.bgSurface0, border: `1px solid ${t.bgSurface1}` }}>
            <div className={styles.sessionsHeader} style={{ borderBottom: `1px solid ${t.bgSurface1}`, color: t.textMuted }}>
              Conversations
            </div>
            {sessions.length === 0 ? (
              <div className={styles.sessionsEmpty} style={{ color: t.textMuted }}>
                No sessions yet.
                <br />
                <span style={{ opacity: 0.6, fontSize: 11 }}>Connect Brightsky to see history.</span>
              </div>
            ) : (
              <div className={styles.sessionsList}>
                {sessions.map((s) => (
                  <button
                    key={s.id}
                    className={styles.sessionItem}
                    style={{ color: t.textPrimary }}
                    onClick={() => { onSelectSession?.(s.id); setSessionsOpen(false) }}
                  >
                    <span className={styles.sessionTitle}>{s.title}</span>
                    <span className={styles.sessionMeta} style={{ color: t.textMuted }}>
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
        <button className={styles.closeBtn} onClick={onToggleChat} aria-label="Close chat panel">
          <X size={14} />
        </button>
      </Tooltip>
    </div>
  )
}
