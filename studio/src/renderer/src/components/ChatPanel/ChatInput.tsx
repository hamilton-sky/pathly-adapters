import { Send, Square } from 'lucide-react'
import { useTheme } from '../../useTheme'
import { useChatStore } from '../../store/chatStore'
import { ModelSelector } from './ModelSelector'
import styles from './ChatInput.module.css'


interface ChatInputProps {
  value: string
  onChange: (v: string) => void
  onSend: () => void
  disabled?: boolean
  isLoading?: boolean
  onStop?: () => void
}

export function ChatInput({ value, onChange, onSend, disabled, isLoading, onStop }: ChatInputProps): JSX.Element {
  const t = useTheme()
  const isEmbedding = useChatStore((s) => s.isEmbedding)
  const embedReady = useChatStore((s) => s.embedReady)
  const embedProgress = useChatStore((s) => s.embedProgress)

  const isModelLoading = !embedReady
  const isDownloading = isModelLoading

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
    <>
    <style>{`
      @keyframes stop-pulse {
        0%, 100% { box-shadow: 0 0 0 0px rgba(234, 179, 8, 0.4); }
        50%       { box-shadow: 0 0 0 4px rgba(234, 179, 8, 0.0); }
      }
    `}</style>
    <div
      className={styles.container}
      style={{ borderTop: t.border, background: t.bgSurface0 }}
    >
      {/* Model loading bar — shown from first mount until model is ready */}
      {isModelLoading && (
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
        disabled={disabled || isDownloading}
        placeholder={isDownloading ? 'Waiting for MiniLM to download…' : 'Message Conductor…'}
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
        <ModelSelector />
        <span
          className={styles.modelPill}
          style={{
            background: t.bgSurface1,
            color: isEmbedding ? t.accent : isDownloading ? t.accent : embedReady ? t.textMuted : t.textMuted,
            fontFamily: t.fontFamilyMono,
          }}
        >
          {isEmbedding
            ? '◈ Routing…'
            : isDownloading
            ? `◈ ${embedProgress}%`
            : embedReady
            ? '◈ MiniLM'
            : '◈ Loading…'}
        </span>
        <button
          className={styles.sendButton}
          onClick={() => {
            if (isLoading) {
              onStop?.()
            } else if (!disabled && value.trim()) {
              onSend()
            }
          }}
          disabled={isLoading ? false : (disabled || !value.trim() || isDownloading)}
          title={isLoading ? 'Stop generating' : 'Send (Enter)'}
          style={isLoading ? {
            background: 'rgba(234, 179, 8, 0.15)',
            color: '#EAB308',
            border: '1px solid rgba(234, 179, 8, 0.3)',
            animation: 'stop-pulse 1.8s ease-in-out infinite',
          } : {
            background: value.trim() && !disabled && !isDownloading ? t.accent : t.bgSurface1,
            color: value.trim() && !disabled && !isDownloading ? '#000' : t.textMuted,
          }}
        >
          <span style={{ position: 'relative', width: 13, height: 13, display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{
              position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
              opacity: isLoading ? 0 : 1, transform: isLoading ? 'scale(0.7)' : 'scale(1)',
              transition: 'opacity 150ms ease, transform 150ms ease',
            }}>
              <Send size={13} />
            </span>
            <span style={{
              position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
              opacity: isLoading ? 1 : 0, transform: isLoading ? 'scale(1)' : 'scale(0.7)',
              transition: 'opacity 150ms ease, transform 150ms ease',
            }}>
              <Square size={13} />
            </span>
          </span>
        </button>
      </div>
    </div>
    </>
  )
}
