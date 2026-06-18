import { useState, useEffect, useRef } from 'react'
import { Cpu, ChevronDown, Check } from 'lucide-react'
import { Tooltip } from '../../../ui'
import { EDITOR_CLIS, EditorCli } from '../editorCli'
import styles from './CliSelect.module.css'

interface Props {
  /** Currently selected engine. */
  value: EditorCli
  /** Pick a new engine (only enabled engines are reported). */
  onChange: (cli: EditorCli) => void
  /** Hide the text label when the header is in compact mode. */
  compact?: boolean
  /** Which edge the menu aligns to — 'right' opens leftward (use inside a modal). */
  align?: 'left' | 'right'
  /** Open the menu upward instead of downward (use when the trigger sits low). */
  up?: boolean
}

// Engine picker for the notebook's one-shot AI actions (AI Split, AI Analyze).
// Mirrors the SplitPill drop-down idiom: trigger pill + click-outside menu.
export default function CliSelect({ value, onChange, compact, align = 'left', up = false }: Props) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const current = EDITOR_CLIS.find((c) => c.id === value) ?? EDITOR_CLIS[0]

  return (
    <div className={styles.cliSelect} ref={ref}>
      <Tooltip label={`AI engine for Split & Analyze — ${current.label}`} placement="bottom">
        <button
          type="button"
          className={styles.trigger}
          aria-haspopup="menu"
          {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
          aria-label={`AI engine: ${current.label}`}
          onClick={() => setOpen((o) => !o)}
        >
          <Cpu size={13} />
          {!compact && <span className={styles.label}>{current.label}</span>}
          <ChevronDown size={11} />
        </button>
      </Tooltip>

      {open && (
        <div className={styles.menu} data-align={align} data-dir={up ? 'up' : 'down'} role="menu">
          <div className={styles.menuHead}>AI engine</div>
          {EDITOR_CLIS.map((c) => (
            <button
              key={c.id}
              type="button"
              role="menuitemradio"
              {...(value === c.id ? { 'aria-checked': 'true' } : { 'aria-checked': 'false' })}
              className={styles.item}
              disabled={!!c.unavailable}
              title={c.unavailable ?? ''}
              onClick={() => { if (!c.unavailable) { onChange(c.id); setOpen(false) } }}
            >
              <span className={styles.check}>{value === c.id ? <Check size={13} /> : null}</span>
              <span className={styles.itemLabel}>{c.label}</span>
              <span className={styles.itemHint}>{c.unavailable ?? c.hint}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
