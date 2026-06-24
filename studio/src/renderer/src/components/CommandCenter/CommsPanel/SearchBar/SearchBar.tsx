import React, { useState } from 'react'
import { Search, X } from 'lucide-react'
import s from './SearchBar.module.css'

export function SearchBar(
  { value, onSearch, onClear }: { value: string; onSearch: (q: string) => void; onClear: () => void },
) {
  const [text, setText] = useState('')
  const submit = (): void => { if (text.trim()) onSearch(text) }
  const clear = (): void => { setText(''); onClear() }
  return (
    <div className={s.bar}>
      <Search size={12} className={s.ico} />
      <input
        className={s.input}
        placeholder="Search this board…"
        value={text}
        onChange={(e) => setText(e.currentTarget.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') submit(); if (e.key === 'Escape') clear() }}
      />
      {value && (
        <button type="button" className={s.clear} aria-label="Clear search" onClick={clear}>
          <X size={12} />
        </button>
      )}
    </div>
  )
}
