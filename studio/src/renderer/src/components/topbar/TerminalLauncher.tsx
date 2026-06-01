import React, { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Terminal, ChevronDown } from 'lucide-react'
import { useStore } from '../../store'
import { useTerminalStore } from '../../store/terminalStore'
import { IconButton } from '../ui'
import { AntigravityIcon, ClaudeIcon, CodexIcon } from '../Terminal/BrandIcons'
import { launchTerminal } from '../../lib/launchTerminal'
import styles from './TopBar.module.css'

export function TerminalLauncher(): JSX.Element {
  const { projectPath } = useStore()
  const { toggle: toggleTerminal, open: terminalOpen, addTab, tabs } = useTerminalStore()

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

  async function launchWithKind(cmd: string | undefined, label: string): Promise<void> {
    setDropdownOpen(false)
    try {
      await launchTerminal({
        command: cmd,
        label,
        pane: 'left',
        projectPath,
        open: terminalOpen,
        toggle: toggleTerminal,
        addTab,
      })
    } catch { /* PTY errors surface in terminal */ }
  }

  return (
    <>
      <div className={styles.terminalSplit}>
        <IconButton onClick={() => toggleTerminal()} title="Toggle terminal" shortcut="Ctrl+`" data-label="Terminal">
          <Terminal size={14} />
        </IconButton>
        <div className={styles.terminalSplitDivider} />
        <button
          ref={chevronRef}
          className={styles.terminalSplitChevron}
          onClick={openDropdown}
          aria-label="Open terminal launcher"
        >
          <ChevronDown size={10} />
        </button>
      </div>
      {dropdownOpen && dropdownPos && createPortal(
        <div
          ref={dropdownRef}
          className={styles.terminalDropdown}
          style={{ position: 'fixed', top: dropdownPos.top, right: dropdownPos.right }}
        >
          <button className={styles.terminalDropdownItem} onClick={() => void launchWithKind(undefined, `Shell ${tabs.length + 1}`)}>
            + Shell
          </button>
          <div className={styles.terminalDropdownDivider} />
          <button className={styles.terminalDropdownItem} onClick={() => void launchWithKind('claude', 'Claude')}>
            <ClaudeIcon size={13} /> Claude Code
          </button>
          <button className={styles.terminalDropdownItem} onClick={() => void launchWithKind('codex', 'Codex')}>
            <CodexIcon size={13} /> Codex
          </button>
          <button className={styles.terminalDropdownItem} onClick={() => void launchWithKind('agy', 'Antigravity')}>
            <AntigravityIcon size={13} /> Antigravity
          </button>
        </div>,
        document.body
      )}
    </>
  )
}
