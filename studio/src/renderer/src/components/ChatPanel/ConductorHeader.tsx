import { useEffect, useRef, useState } from 'react'
import { X, Zap, Trash2 } from 'lucide-react'
import type { TerminalKind } from '../../store/chatStore'
import { Tooltip } from '../ui'
import { ClaudeIcon, CodexIcon, ShellIcon } from '../Terminal/BrandIcons'
import styles from './ConductorHeader.module.css'

interface ConductorHeaderProps {
  hasClaudeTab: boolean
  hasCodexTab: boolean
  hasShellTab: boolean
  targetKind: TerminalKind
  onSetTarget: (kind: TerminalKind) => void
  onToggleChat: () => void
  onClearChat: () => void
}

export function ConductorHeader({ hasClaudeTab, hasCodexTab, hasShellTab, targetKind, onSetTarget, onToggleChat, onClearChat }: ConductorHeaderProps): JSX.Element {
  const headerRef = useRef<HTMLDivElement>(null)
  const [compact, setCompact] = useState(false)

  useEffect(() => {
    const el = headerRef.current
    if (!el) return

    const update = (): void => {
      setCompact(el.getBoundingClientRect().width < 360)
    }

    update()

    if (typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const targetPills: Array<{
    kind: TerminalKind
    label: string
    icon: JSX.Element
    active: boolean
  }> = [
    { kind: 'claude', label: 'claude', icon: <ClaudeIcon size={14} />, active: hasClaudeTab },
    { kind: 'codex', label: 'codex', icon: <CodexIcon size={14} />, active: hasCodexTab },
    { kind: 'shell', label: 'shell', icon: <ShellIcon size={14} />, active: hasShellTab },
  ]

  return (
    <div ref={headerRef} className={styles.header}>
      <div className={styles.titleRow}>
        <span className={styles.title}>
          <Zap size={13} /> Conductor
        </span>
      </div>

      <div className={styles.pills}>
        {targetPills.map((pill) => (
          <Tooltip
            key={pill.kind}
            label={`Focus ${pill.label} terminal`}
            placement="bottom"
          >
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

      <Tooltip label="Clear chat session" shortcut="Esc" placement="bottom">
        <button
          className={styles.closeBtn}
          onClick={onClearChat}
          aria-label="Clear chat session"
          title="Clear chat"
        >
          <Trash2 size={13} />
        </button>
      </Tooltip>

      <Tooltip label="Close chat panel" placement="bottom">
        <button
          className={styles.closeBtn}
          onClick={onToggleChat}
          aria-label="Close chat panel"
        >
          <X size={14} />
        </button>
      </Tooltip>
    </div>
  )
}
