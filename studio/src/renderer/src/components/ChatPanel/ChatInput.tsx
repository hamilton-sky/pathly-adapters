import { useTheme } from '../../useTheme'
import styles from './ChatInput.module.css'

interface ChatInputProps {
  value: string
  onChange: (v: string) => void
  onSend: () => void
  disabled?: boolean
}

export function ChatInput({ value, onChange, onSend, disabled }: ChatInputProps): JSX.Element {
  const t = useTheme()

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
      <textarea
        className={styles.textarea}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder="Message Conductor…"
        rows={1}
        style={{
          color: t.textPrimary,
          background: t.bgBase,
          border: t.border,
          fontFamily: t.fontFamilyBase,
          caretColor: t.accent,
        }}
      />
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
    </div>
  )
}
