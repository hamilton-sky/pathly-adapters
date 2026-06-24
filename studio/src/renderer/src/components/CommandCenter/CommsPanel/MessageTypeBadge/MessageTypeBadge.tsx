import React from 'react'
import { Star, FileText } from 'lucide-react'
import type { MessageType } from '../../types'
import s from './MessageTypeBadge.module.css'

// Notebook-cell-style type chip — a tinted mono badge that carries the message
// type. Colours come from data-type CSS selectors in the parent card's module.
export function MessageTypeBadge({ type }: { type: MessageType }) {
  const lead =
    type === 'decision' ? <Star size={10} /> :
    type === 'artifact' ? <FileText size={10} /> :
    null
  return (
    <div className={s.badge} data-type={type}>
      {lead}
      {type}
    </div>
  )
}
