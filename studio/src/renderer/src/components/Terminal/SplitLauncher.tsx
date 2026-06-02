import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Check, ChevronDown } from 'lucide-react'
import type { TerminalKind } from '../../store/chatStore'
import { TERMINAL_OPTIONS } from '../../lib/terminalOptions'
import styles from './Terminal.module.css'

interface SplitLauncherProps {
  pane: 'left' | 'right'
  onAddTab: (pane: 'left' | 'right') => void
  onLaunch: (cmd: string | undefined, label: string, pane: 'left' | 'right') => void
}

export function SplitLauncher({ pane, onAddTab, onLaunch }: SplitLauncherProps): JSX.Element {
  const [lastUsedKind, setLastUsedKind] = useState<TerminalKind>('shell')
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [dropdownPos, setDropdownPos] = useState<{ top: number; right: number } | null>(null)
  const chevronRef = useRef<HTMLButtonElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!dropdownOpen) return
    function handleMouseDown(e: MouseEvent): void {
      if (
        dropdownRef.current && !dropdownRef.current.contains(e.target as Node) &&
        chevronRef.current && !chevronRef.current.contains(e.target as Node)
      ) {
        setDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleMouseDown)
    return () => document.removeEventListener('mousedown', handleMouseDown)
  }, [dropdownOpen])

  function openDropdown(): void {
    if (chevronRef.current) {
      const rect = chevronRef.current.getBoundingClientRect()
      setDropdownPos({ top: rect.bottom + 4, right: window.innerWidth - rect.right })
    }
    setDropdownOpen((v) => !v)
  }

  function launchKind(kind: TerminalKind): void {
    const opt = TERMINAL_OPTIONS.find((o) => o.kind === kind)
    if (!opt) return
    if (kind === 'shell') {
      onAddTab(pane)
    } else {
      onLaunch(opt.command, opt.label, pane)
    }
  }

  function selectFromDropdown(kind: TerminalKind): void {
    setLastUsedKind(kind)
    setDropdownOpen(false)
    launchKind(kind)
  }

  const activeOpt = TERMINAL_OPTIONS.find((o) => o.kind === lastUsedKind) ?? TERMINAL_OPTIONS[0]

  return (
    <div className={styles.splitLauncher}>
      <button
        type="button"
        className={styles.splitLauncherMain}
        aria-label={`Launch ${activeOpt.label}`}
        onClick={() => launchKind(lastUsedKind)}
      >
        {activeOpt.icon(13)}
      </button>
      <div className={styles.splitLauncherDivider} />
      <button
        ref={chevronRef}
        type="button"
        className={styles.splitLauncherChevron}
        aria-label="Choose terminal type"
        {...(dropdownOpen ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
        onClick={openDropdown}
      >
        <ChevronDown size={10} />
      </button>
      {dropdownOpen && dropdownPos && createPortal(
        <div
          ref={dropdownRef}
          className={styles.launcherDropdown}
          style={{ position: 'fixed', top: dropdownPos.top, right: dropdownPos.right }}
        >
          {TERMINAL_OPTIONS.map((opt) => (
            <button
              key={opt.kind}
              type="button"
              className={`${styles.launcherDropdownItem}${opt.kind === lastUsedKind ? ` ${styles.launcherDropdownItemActive}` : ''}`}
              onClick={() => selectFromDropdown(opt.kind)}
            >
              {opt.icon(13)}
              {opt.label}
              {opt.kind === lastUsedKind && (
                <Check size={11} className={styles.launcherDropdownCheck} />
              )}
            </button>
          ))}
        </div>,
        document.body
      )}
    </div>
  )
}
