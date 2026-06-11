import React, { useState, useRef } from 'react'
import { Send } from 'lucide-react'
import type { BoardScope, MessageType } from '../CommandCenter/types'
import { COMPOSE_TYPES } from '../CommandCenter/constants'
import s from './CommsInput.module.css'

export interface CommsInputProps {
  scope: BoardScope
  mainFeature: string
  onSend: (type: MessageType, text: string) => void
}

const PLACEHOLDER: Record<BoardScope, (f: string) => string> = {
  feature: (f) => `Message ${f}…`,
  project: () => 'Project decision or broadcast…',
  global: () => 'Global policy (permanent, all agents)…',
}

// Compose bar + message-type picker. Cmd/Ctrl+Enter sends.
export function CommsInput({ scope, mainFeature, onSend }: CommsInputProps) {
  const [text, setText] = useState('')
  const [type, setType] = useState<MessageType>(scope === 'feature' ? 'nudge' : 'decision')
  const ta = useRef<HTMLTextAreaElement>(null)

  const send = () => {
    const t = text.trim()
    if (!t) return
    onSend(type, t)
    setText('')
    if (ta.current) ta.current.style.height = 'auto'
  }

  const grow = (el: HTMLTextAreaElement) => {
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 96)}px`
  }

  return (
    <div className={s.compose}>
      <div className={s.composeField}>
        <textarea
          ref={ta}
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
        <div className={s.composeBar}>
          <select
            className={s.typePick}
            value={type}
            onChange={(e) => setType(e.target.value as MessageType)}
          >
            {COMPOSE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
      </div>
      <button
        type="button"
        className={s.composeSend}
        disabled={!text.trim()}
        onClick={send}
      >
        <Send size={13} />Send
      </button>
    </div>
  )
}
