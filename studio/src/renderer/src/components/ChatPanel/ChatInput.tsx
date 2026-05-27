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
            disabled={disabled || !value.trim() || isDownloading}
            title="Send (Enter)"
            style={{
              background: value.trim() && !disabled && !isDownloading ? t.accent : t.bgSurface1,
              color: value.trim() && !disabled && !isDownloading ? '#000' : t.textMuted,
            }}
          >
            <Send size={13} />
          </button>
        )}
      </div>
    </div>
  )
}
