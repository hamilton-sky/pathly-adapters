import React, { useState, useRef } from 'react'
import { Send, Paperclip } from 'lucide-react'
import type { BoardScope, MessageType } from '../CommandCenter/types'
import { TypePicker } from './TypePicker'
import s from './CommsInput.module.css'

export interface CommsInputProps {
  scope: BoardScope
  mainFeature: string
  type: MessageType
  onTypeChange: (t: MessageType) => void
  onSend: (text: string) => void
}

const PLACEHOLDER: Record<BoardScope, (f: string) => string> = {
  feature: (f) => `Message ${f}…`,
  project: () => 'Project decision or broadcast…',
  global: () => 'Global policy (permanent, all agents)…',
}

// Compose box: textarea + toolbar (type-picker · attach · send).
// TypePicker drop-up opens above the toolbar — composeBox must NOT use
// overflow:hidden or it will clip the menu.
export function CommsInput({ scope, mainFeature, type, onTypeChange, onSend }: CommsInputProps) {
  const [text, setText] = useState('')
  const ta = useRef<HTMLTextAreaElement>(null)

  const send = () => {
    const t = text.trim()
    if (!t) return
    onSend(t)
    setText('')
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
        value={text}
        onChange={(e) => { setText(e.target.value); grow(e.target) }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
            e.preventDefault()
            send()
          }
        }}
      />
      <div className={s.toolbar}>
        <TypePicker value={type} onChange={onTypeChange} />
        <button
          type="button"
          className={s.toolbarBtn}
          title="Attach artifact (coming soon)"
          aria-label="Attach artifact"
          disabled
        >
          <Paperclip size={12} />
        </button>
        <button
          type="button"
          className={s.sendBtn}
          disabled={!text.trim()}
          onClick={send}
          title="Send (Ctrl+Enter)"
          aria-label="Send message"
        >
          <Send size={11} />
          <span>Send</span>
        </button>
      </div>
    </div>
  )
}
