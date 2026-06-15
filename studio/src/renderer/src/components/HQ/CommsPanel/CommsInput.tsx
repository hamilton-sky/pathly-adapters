import { useRef } from 'react'
import { Send, Paperclip } from 'lucide-react'
import type { BoardScope, Message, MessageType } from '../../CommandCenter/types'
import { TypePicker } from './TypePicker'
import s from './CommsInput.module.css'

export interface CommsInputProps {
  scope: BoardScope
  mainFeature: string
  type: MessageType
  onTypeChange: (t: MessageType) => void
  onSend: (text: string) => void
  onAttachPath?: (path: string, atype?: Message['atype']) => void
  /** Compose text is owned by the panel so Start can post it before running. */
  value: string
  onChange: (v: string) => void
}

const PLACEHOLDER: Record<BoardScope, (f: string) => string> = {
  feature: (f) => `Message ${f}…`,
  project: () => 'Project decision or broadcast…',
  global: () => 'Global policy (permanent, all agents)…',
}

function inferAtype(name: string): 'md' | 'code' | 'pdf' | 'image' | 'json' {
  const ext = name.split('.').pop()?.toLowerCase() ?? ''
  if (ext === 'md') return 'md'
  if (ext === 'pdf') return 'pdf'
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext)) return 'image'
  if (ext === 'json') return 'json'
  return 'code'
}

// Compose box: textarea + toolbar (type-picker · attach · send).
// TypePicker drop-up opens above the toolbar — composeBox must NOT use
// overflow:hidden or it will clip the menu.
export function CommsInput({ scope, mainFeature, type, onTypeChange, onSend, onAttachPath, value, onChange }: CommsInputProps) {
  const ta = useRef<HTMLTextAreaElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const send = () => {
    const t = value.trim()
    if (!t) return
    onSend(t)
    if (ta.current) ta.current.style.height = 'auto'
  }

  const grow = (el: HTMLTextAreaElement) => {
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 96)}px`
  }

  return (
    <div className={s.composeBox}>
      <textarea
        ref={ta}
        className={s.textarea}
        rows={1}
        placeholder={PLACEHOLDER[scope](mainFeature)}
        value={value}
        onChange={(e) => { onChange(e.target.value); grow(e.target) }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
            e.preventDefault()
            send()
          }
        }}
      />
      <div className={s.toolbar}>
        <TypePicker value={type} onChange={onTypeChange} />
        <input
          ref={fileRef}
          type="file"
          className={s.hiddenFile}
          onChange={(e) => {
            const f = e.currentTarget.files?.[0]
            if (f && onAttachPath) onAttachPath(f.name, inferAtype(f.name))
            e.currentTarget.value = ''
          }}
        />
        <button
          type="button"
          className={s.toolbarBtn}
          title="Attach artifact"
          aria-label="Attach artifact"
          onClick={() => fileRef.current?.click()}
        >
          <Paperclip size={12} />
        </button>
        <button
          type="button"
          className={s.sendBtn}
          disabled={!value.trim()}
          onClick={send}
          title="Send (Ctrl+Enter)"
          aria-label="Send message"
        >
          <Send size={13} />
        </button>
      </div>
    </div>
  )
}
