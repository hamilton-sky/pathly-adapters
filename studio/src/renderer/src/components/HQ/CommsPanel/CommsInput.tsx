import React, { useState, useRef } from 'react'
import { Send } from 'lucide-react'
import type { BoardScope } from '../CommandCenter/types'
import s from './CommsInput.module.css'

export interface CommsInputProps {
  scope: BoardScope
  mainFeature: string
  onSend: (text: string) => void
}

const PLACEHOLDER: Record<BoardScope, (f: string) => string> = {
  feature: (f) => `Message ${f}…`,
  project: () => 'Project decision or broadcast…',
  global: () => 'Global policy (permanent, all agents)…',
}

// Compose row: textarea + send. Cmd/Ctrl+Enter sends. The message-type picker
// lives above the input, in the CommsPanel controls row.
export function CommsInput({ scope, mainFeature, onSend }: CommsInputProps) {
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
    el.style.height = `${Math.min(el.scrollHeight, 72)}px`
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
      </div>
      <button
        type="button"
        className={s.composeSend}
        disabled={!text.trim()}
        onClick={send}
        title="Send (Ctrl+Enter)"
      >
        <Send size={12} />Send
      </button>
    </div>
  )
}
