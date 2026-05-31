import { useState, useRef, useEffect } from 'react'
import { Send, Square, TerminalSquare, ChevronUp } from 'lucide-react'
import { useChatStore } from '../../../store/chatStore'
import { ModelSelector } from '../ModelSelector/ModelSelector'
import { ClaudeIcon, CodexIcon, ShellIcon } from '../../Terminal/BrandIcons'
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
  miniTerminalKind?: 'claude' | 'codex' | 'shell'
}

export function ChatInput({ value, onChange, onSend, disabled, isLoading, onStop, onToggleMiniTerminal, onLaunchMiniTerminal, miniTerminalActive, miniTerminalKind }: ChatInputProps): JSX.Element {
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

  const pillIsActive = isEmbedding || isRouterLoading

  return (
    <div className={styles.container}>
      {/* Model loading bar — shown from first mount until model is ready */}
      {isRouterLoading && (
        <div className={styles.downloadBar}>
          <div className={styles.downloadLabel}>
            {embedProgress > 0
              ? `⬇ Downloading MiniLM… ${embedProgress}%`
              : '⬇ Loading MiniLM routing model…'}
          </div>
          <progress
            className={`${styles.progressBar} ${embedProgress === 0 ? styles.progressBarPulsing : ''}`}
            value={embedProgress > 0 ? embedProgress : undefined}
            max={100}
          />
        </div>
      )}

      <textarea
        className={styles.textarea}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder="Message..."
        rows={1}
      />
      <div className={styles.footer}>
        <div ref={groupRef} className={styles.terminalGroup}>
          {dropdownOpen && (
            <div className={styles.terminalDropdown}>
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
                    type="button"
                    className={styles.terminalDropdownItem}
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
            type="button"
            className={styles.terminalBtn}
            data-kind={miniTerminalKind}
            onClick={() => {
              if (miniTerminalKind) {
                onToggleMiniTerminal?.()
              } else {
                onLaunchMiniTerminal?.('shell')
              }
            }}
            title={miniTerminalKind ? (miniTerminalActive ? 'Hide terminal' : 'Show terminal') : 'Open terminal'}
          >
            <TerminalSquare size={14} />
          </button>
          <div className={styles.terminalSep} />
          <button
            type="button"
            className={styles.terminalChevron}
            onClick={() => setDropdownOpen((v) => !v)}
            title="Choose terminal type"
          >
            <ChevronUp size={10} />
          </button>
        </div>
        <ModelSelector />
        <span
          className={`${styles.modelPill} ${pillIsActive ? styles.modelPillActive : ''}`}
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
            type="button"
            className={`${styles.sendButton} ${styles.sendButtonStop}`}
            onClick={() => onStop?.()}
            title="Stop"
          >
            <Square size={13} />
          </button>
        ) : (
          <button
            type="button"
            className={`${styles.sendButton} ${value.trim() && !disabled ? styles.sendButtonActive : styles.sendButtonIdle}`}
            onClick={() => { if (!disabled && value.trim()) onSend() }}
            disabled={disabled || !value.trim()}
            title="Send (Enter)"
          >
            <Send size={13} />
          </button>
        )}
      </div>
    </div>
  )
}
