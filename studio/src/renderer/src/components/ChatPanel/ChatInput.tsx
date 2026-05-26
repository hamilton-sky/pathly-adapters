import { Send } from 'lucide-react'
import { useTheme } from '../../useTheme'
import { useChatStore } from '../../store/chatStore'
import { useModelStore } from '../../store/modelStore'
import { WEB_LLM_MODELS } from '../../data/models'
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

  const selectedModelId = useModelStore((s) => s.selectedModelId)
  const cachedModelIds = useModelStore((s) => s.cachedModelIds)
  const isModelCached = cachedModelIds.includes(selectedModelId)
  const selectedModel = WEB_LLM_MODELS.find((m) => m.id === selectedModelId)
  const modelShortName = selectedModel?.name ?? selectedModelId

  // Show loading state as soon as the component mounts and model isn't ready yet.
  // embedProgress=0 means "started but first callback not fired yet" — still loading.
  const isModelLoading = !embedReady
  const isDownloading = isModelLoading  // kept as alias for clarity below

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>): void {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (!disabled && value.trim() && isModelCached) {
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
        disabled={disabled || isDownloading || !isModelCached}
        placeholder={isDownloading ? 'Waiting for MiniLM to download…' : !isModelCached ? `Download ${modelShortName} to start chatting…` : 'Message Conductor…'}
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
            opacity: isModelCached ? 1 : 0.5,
          }}
        >
          {isModelCached ? modelShortName : `${modelShortName} — download required`}
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
          onClick={() => { if (!disabled && value.trim() && isModelCached) onSend() }}
          disabled={disabled || !value.trim() || isDownloading || !isModelCached}
          title="Send (Enter)"
          style={{
            background: value.trim() && !disabled && !isDownloading && isModelCached ? t.accent : t.bgSurface1,
            color: value.trim() && !disabled && !isDownloading && isModelCached ? '#000' : t.textMuted,
          }}
        >
          <Send size={13} />
        </button>
      </div>
    </div>
  )
}
