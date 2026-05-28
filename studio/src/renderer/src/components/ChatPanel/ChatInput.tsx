import { useState, useRef, useEffect } from 'react'
import { Send, Square, TerminalSquare, ChevronUp } from 'lucide-react'
import { useTheme } from '../../useTheme'
import { useChatStore } from '../../store/chatStore'
import { ModelSelector } from './ModelSelector'
import { ClaudeIcon, CodexIcon, ShellIcon } from '../Terminal/BrandIcons'
import styles from './ChatInput.module.css'


interface ChatInputProps {
  value: string
  onChange: (v: string) => void
  onSend: () => void
  disabled?: boolean
  isLoading?: boolean
  onStop?: () => void
  onToggleMiniTerminal?: () => void
  onLaunchMiniTerminal?: (kind: 'shell' | 'claude' | 'codex') => void
  miniTerminalActive?: boolean
  miniTerminalColor?: string
}

export function ChatInput({ value, onChange, onSend, disabled, isLoading, onStop, onToggleMiniTerminal, onLaunchMiniTerminal, miniTerminalActive, miniTerminalColor }: ChatInputProps): JSX.Element {
  const t = useTheme()
  const isEmbedding = useChatStore((s) => s.isEmbedding)
  const embedReady = useChatStore((s) => s.embedReady)
  const embedProgress = useChatStore((s) => s.embedProgress)
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const groupRef = useRef<HTMLDivElement>(null)

  const isRouterLoading = !embedReady

  useEffect(() => {
    if (!dropdownOpen) return
    const handler = (e: MouseEvent): void => {
      if (!groupRef.current?.contains(e.target as Node)) setDropdownOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [dropdownOpen])

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>): void {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (isLoading) return
      if (!disabled && value.trim()) {
        onSend()
      }
    }
  }

  return (
    <div
      className={styles.container}
      style={{ borderTop: t.border, background: t.bgSurface0 }}
    >
      {/* Model loading bar — shown from first mount until model is ready */}
      {isRouterLoading && (
        <div className={styles.downloadBar}>
          <div className={styles.downloadLabel} style={{ color: t.textMuted, fontFamily: t.fontFamilyMono }}>
            {embedProgress > 0
              ? `⬇ Downloading MiniLM… ${embedProgress}%`
              : '⬇ Loading MiniLM routing model…'}
          </div>
          <div className={styles.progressTrack} style={{ background: t.bgSurface1 }}>
            <div
              className={styles.progressFill}
              style={{
                width: embedProgress > 0 ? `${embedProgress}%` : '100%',
                background: t.accent,
                opacity: embedProgress > 0 ? 1 : 0.35,
                animation: embedProgress === 0 ? 'pulse 1.5s ease-in-out infinite' : 'none',
              }}
            />
          </div>
        </div>
      )}

      <textarea
        className={styles.textarea}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder="Message Conductor..."
        rows={1}
        style={{
          color: t.textPrimary,
          background: t.bgBase,
          border: t.border,
          fontFamily: t.fontFamilyBase,
          caretColor: t.accent,
        }}
      />
      <div className={styles.footer}>
        <div ref={groupRef} className={styles.terminalGroup} style={{ border: `1px solid ${t.bgSurface1}` }}>
          {dropdownOpen && (
            <div
              className={styles.terminalDropdown}
              style={{ background: t.bgSurface0, border: `1px solid ${t.bgSurface1}` }}
            >
              {(['shell', 'claude', 'codex'] as const).map((kind) => {
                const labels = { shell: '+ Shell', claude: 'Claude Code', codex: 'Codex' }
                const icons = {
                  shell: <ShellIcon size={14} />,
                  claude: <ClaudeIcon size={14} />,
                  codex: <CodexIcon size={14} />,
                }
                return (
                  <button
                    key={kind}
                    className={styles.terminalDropdownItem}
                    style={{ color: t.textSecondary, fontFamily: t.fontFamilyMono }}
                    onClick={() => {
                      setDropdownOpen(false)
                      onLaunchMiniTerminal?.(kind)
                    }}
                  >
                    {icons[kind]}
                    {labels[kind]}
                  </button>
                )
              })}
            </div>
          )}
          <button
            className={styles.terminalBtn}
            onClick={() => {
              if (miniTerminalColor) {
                onToggleMiniTerminal?.()
              } else {
                onLaunchMiniTerminal?.('shell')
              }
            }}
            title={miniTerminalColor ? (miniTerminalActive ? 'Hide terminal' : 'Show terminal') : 'Open terminal'}
            style={{ color: miniTerminalColor ?? undefined }}
          >
            <TerminalSquare size={14} />
          </button>
          <div style={{ width: 1, height: 16, background: t.bgSurface1, flexShrink: 0 }} />
          <button
            className={styles.terminalChevron}
            onClick={() => setDropdownOpen((v) => !v)}
            title="Choose terminal type"
            style={{ color: t.textMuted }}
          >
            <ChevronUp size={10} />
          </button>
        </div>
        <ModelSelector />
        <span
          className={styles.modelPill}
          style={{
            background: t.bgSurface1,
            color: isEmbedding ? t.accent : isRouterLoading ? t.accent : embedReady ? t.textMuted : t.textMuted,
            fontFamily: t.fontFamilyMono,
          }}
        >
          {isEmbedding
            ? '◈ Routing…'
            : isRouterLoading
            ? `◈ ${embedProgress}%`
            : embedReady
            ? '◈ MiniLM'
            : '◈ Loading…'}
        </span>
        {isLoading ? (
          <button
            className={styles.sendButton}
            onClick={() => onStop?.()}
            title="Stop"
            style={{ background: '#EAB308', color: '#000' }}
          >
            <Square size={13} />
          </button>
        ) : (
          <button
            className={styles.sendButton}
            onClick={() => { if (!disabled && value.trim()) onSend() }}
            disabled={disabled || !value.trim()}
            title="Send (Enter)"
            style={{
              background: value.trim() && !disabled ? t.accent : t.bgSurface1,
              color: value.trim() && !disabled ? '#000' : t.textMuted,
            }}
          >
            <Send size={13} />
          </button>
        )}
      </div>
    </div>
  )
}
