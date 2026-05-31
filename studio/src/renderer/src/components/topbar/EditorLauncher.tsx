import React, { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ChevronDown } from 'lucide-react'
import { useStore } from '../../store'
import { useToastStore } from '../../store/toastStore'
import { Tooltip } from '../ui'
import { FileExplorerIcon, WindowsTerminalIcon, GitBashIcon, WslIcon, PyCharmIcon } from '../Terminal/BrandIcons'
import styles from './TopBar.module.css'

function VsCodeIcon({ size = 14, style }: { size?: number; style?: React.CSSProperties }): JSX.Element {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" style={style}>
      <path d="M23.15 2.587L18.21.21a1.494 1.494 0 00-1.705.29l-9.46 8.63-4.12-3.128a.999.999 0 00-1.276.057L.327 7.261A1 1 0 00.326 8.74L3.9 12 .326 15.26a1 1 0 00.001 1.479L1.65 17.94a.999.999 0 001.276.057l4.12-3.128 9.46 8.63a1.492 1.492 0 001.704.29l4.942-2.377A1.5 1.5 0 0024 20.06V3.939a1.5 1.5 0 00-.85-1.352zm-5.146 14.861L10.826 12l7.178-5.448v10.896z" />
    </svg>
  )
}

function ipcErrMsg(err: unknown): string {
  const raw = err instanceof Error ? err.message : String(err)
  return raw.replace(/^Error invoking remote method '[^']+': (Error: )?/, '')
}

export function EditorLauncher(): JSX.Element {
  const { projectPath } = useStore()
  const pushToast = useToastStore((s) => s.push)

  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [dropdownPos, setDropdownPos] = useState<{ top: number; left: number } | null>(null)
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
      setDropdownPos({ top: rect.bottom + 4, left: rect.left })
    }
    setDropdownOpen((v) => !v)
  }

  async function openVsCode(): Promise<void> {
    try {
      await window.pathly.shell.openVsCode(projectPath)
    } catch (err) {
      pushToast(ipcErrMsg(err), 'error')
    }
  }

  async function launchInApp(appType: string): Promise<void> {
    setDropdownOpen(false)
    try {
      await window.pathly.shell.openInApp(projectPath, appType)
    } catch (err) {
      pushToast(ipcErrMsg(err), 'error')
    }
  }

  if (!projectPath) return <></>

  return (
    <>
      <div className={styles.vsCodeSplit}>
        <Tooltip label="Open in VS Code" placement="bottom">
          <button className={styles.vsCodeSplitMain} onClick={() => void openVsCode()} aria-label="Open in VS Code">
            <VsCodeIcon size={14} style={{ color: '#007ACC' }} />
          </button>
        </Tooltip>
        <div className={styles.vsCodeSplitDivider} />
        <button ref={chevronRef} className={styles.vsCodeSplitChevron} onClick={openDropdown} aria-label="Open project in…">
          <ChevronDown size={10} />
        </button>
      </div>
      {dropdownOpen && dropdownPos && createPortal(
        <div
          ref={dropdownRef}
          className={styles.vsCodeDropdown}
          style={{ position: 'fixed', top: dropdownPos.top, left: dropdownPos.left }}
        >
          <div className={styles.vsCodeDropdownLabel}>Open project in…</div>
          <div className={styles.vsCodeDropdownDivider} />
          <button className={styles.vsCodeDropdownItem} onClick={() => void launchInApp('vscode')}>
            <VsCodeIcon size={15} style={{ color: '#007ACC' }} /> VS Code
          </button>
          <button className={styles.vsCodeDropdownItem} onClick={() => void launchInApp('explorer')}>
            <FileExplorerIcon size={15} /> File Explorer
          </button>
          <button className={styles.vsCodeDropdownItem} onClick={() => void launchInApp('terminal')}>
            <WindowsTerminalIcon size={15} /> Terminal
          </button>
          <button className={styles.vsCodeDropdownItem} onClick={() => void launchInApp('gitbash')}>
            <GitBashIcon size={15} /> Git Bash
          </button>
          <button className={styles.vsCodeDropdownItem} onClick={() => void launchInApp('wsl')}>
            <WslIcon size={15} /> WSL
          </button>
          <button className={styles.vsCodeDropdownItem} onClick={() => void launchInApp('pycharm')}>
            <PyCharmIcon size={15} /> PyCharm
          </button>
        </div>,
        document.body
      )}
    </>
  )
}
