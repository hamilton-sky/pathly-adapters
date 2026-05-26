import { Send } from 'lucide-react'
import { useTheme } from '../../useTheme'
import { useChatStore } from '../../store/chatStore'
import styles from './ChatInput.module.css'

interface ChatInputProps {
  value: string
  onChange: (v: string) => void
  onSend: () => void
  disabled?: boolean
}

export function ChatInput({ value, onChange, onSend, disabled }: ChatInputProps): JSX.Element {
  const t = useTheme()
  const isEmbedding = useChatStore((s) => s.isEmbedding)
  const embedReady = useChatStore((s) => s.embedReady)
  const embedProgress = useChatStore((s) => s.embedProgress)

  const isDownloading = !embedReady && embedProgress > 0 && embedProgress < 100

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>): void {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
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
      {/* Model download progress bar — only shown while downloading */}
      {isDownloading && (
        <div className={styles.downloadBar}>
          <div className={styles.downloadLabel} style={{ color: t.textMuted, fontFamily: t.fontFamilyMono }}>
            ⬇ Downloading MiniLM… {embedProgress}%
          </div>
          <div className={styles.progressTrack} style={{ background: t.bgSurface1 }}>
            <div
              className={styles.progressFill}
              style={{ width: `${embedProgress}%`, background: t.accent }}
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
        <span
          className={styles.modelPill}
          style={{
            background: t.bgSurface1,
            color: t.textMuted,
            fontFamily: t.fontFamilyMono,
          }}
        >
          phi-4 mini
        </span>
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
      </div>
    </div>
  )
}
