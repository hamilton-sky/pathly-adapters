import React, { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Terminal, ChevronDown, X, Moon, Sun, Menu, LayoutGrid, List, Activity, Brain, Copy } from 'lucide-react'
import { useStore } from '../store'
import { useUiStore } from '../store/uiStore'
import { isLightPalette } from '../theme'
import { useTerminalStore } from '../store/terminalStore'
import { listDirs, publish, onPublishOutput } from '../services/pathlyApi'
import { IconButton, Tooltip } from './ui'
import { ClaudeIcon, CodexIcon, FileExplorerIcon, WindowsTerminalIcon, GitBashIcon, WslIcon, PyCharmIcon } from './Terminal/BrandIcons'
import { launchTerminal } from '../lib/launchTerminal'
import styles from './TopBar.module.css'


function VsCodeIcon({ size = 14, style }: { size?: number; style?: React.CSSProperties }): JSX.Element {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" style={style}>
      <path d="M23.15 2.587L18.21.21a1.494 1.494 0 00-1.705.29l-9.46 8.63-4.12-3.128a.999.999 0 00-1.276.057L.327 7.261A1 1 0 00.326 8.74L3.9 12 .326 15.26a1 1 0 00.001 1.479L1.65 17.94a.999.999 0 001.276.057l4.12-3.128 9.46 8.63a1.492 1.492 0 001.704.29l4.942-2.377A1.5 1.5 0 0024 20.06V3.939a1.5 1.5 0 00-.85-1.352zm-5.146 14.861L10.826 12l7.178-5.448v10.896z"/>
    </svg>
  )
}

export function TopBar(): JSX.Element {
  const {
    projectPath,
    activeTopic,
    monitorSource,
    publishing,
    publishLog,
    theme,
    preferredDark,
    preferredLight,
    activePanel,
    sidebarCollapsed,
    setProjectPath,
    setActiveTopic,
    setPublishing,
    appendPublishLog,
    clearPublishLog,
    setTheme,
    setActivePanel,
    setSidebarCollapsed,
  } = useStore()

  const [activeTopics,   setActiveTopics]   = useState<string[]>([])
  const [showLog, setShowLog] = useState(false)
  const logEndRef = useRef<HTMLDivElement>(null)
  const removeListenerRef = useRef<(() => void) | null>(null)

  useEffect(() => {
    if (!projectPath) return
    let cancelled = false
    async function loadTopics(): Promise<void> {
      try {
        const plansBase = projectPath + '/pathly/plans'
        const [planActive, debugTopics, exploreTopics] = await Promise.all([
          listDirs(plansBase).catch(() => [] as string[]),
          listDirs(projectPath + '/pathly/debugs').catch(() => [] as string[]),
          listDirs(projectPath + '/pathly/explorations').catch(() => [] as string[]),
        ])
        if (!cancelled) {
          const planNames = planActive.filter((e) => e !== '.archive')
          const extra = [...debugTopics, ...exploreTopics].filter((t) => !planNames.includes(t))
          setActiveTopics([...planNames, ...extra])
        }
      } catch { /* directory may not exist yet */ }
    }
    loadTopics()
    const interval = setInterval(loadTopics, 5000)
    return () => { cancelled = true; clearInterval(interval) }
  }, [projectPath])

  useEffect(() => {
    if (logEndRef.current) logEndRef.current.scrollIntoView({ behavior: 'smooth' })
  }, [publishLog])

  async function handlePublish(): Promise<void> {
    clearPublishLog()
    setShowLog(true)
    setPublishing(true)
    if (removeListenerRef.current) removeListenerRef.current()
    removeListenerRef.current = onPublishOutput((line) => appendPublishLog(line))
    try {
      await publish(projectPath)
    } finally {
      setPublishing(false)
      removeListenerRef.current?.()
      removeListenerRef.current = null
    }
  }

  const { toggle: toggleTerminal, open: terminalOpen, addTab, tabs } = useTerminalStore()
  const { chatOpen, toggleChat } = useUiStore()

  const [terminalDropdownOpen, setTerminalDropdownOpen] = useState(false)
  const [terminalDropdownPos, setTerminalDropdownPos] = useState<{ top: number; right: number } | null>(null)
  const terminalChevronRef = useRef<HTMLButtonElement>(null)
  const terminalDropdownRef = useRef<HTMLDivElement>(null)

  const [vsCodeDropdownOpen, setVsCodeDropdownOpen] = useState(false)
  const [vsCodeDropdownPos, setVsCodeDropdownPos] = useState<{ top: number; left: number } | null>(null)
  const vsCodeChevronRef = useRef<HTMLButtonElement>(null)
  const vsCodeDropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!terminalDropdownOpen) return
    function handleMouseDown(e: MouseEvent): void {
      if (
        terminalDropdownRef.current && !terminalDropdownRef.current.contains(e.target as Node) &&
        terminalChevronRef.current && !terminalChevronRef.current.contains(e.target as Node)
      ) {
        setTerminalDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleMouseDown)
    return () => document.removeEventListener('mousedown', handleMouseDown)
  }, [terminalDropdownOpen])

  useEffect(() => {
    if (!vsCodeDropdownOpen) return
    function handleMouseDown(e: MouseEvent): void {
      if (
        vsCodeDropdownRef.current && !vsCodeDropdownRef.current.contains(e.target as Node) &&
        vsCodeChevronRef.current && !vsCodeChevronRef.current.contains(e.target as Node)
      ) {
        setVsCodeDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleMouseDown)
    return () => document.removeEventListener('mousedown', handleMouseDown)
  }, [vsCodeDropdownOpen])

  function openVsCodeDropdown(): void {
    if (vsCodeChevronRef.current) {
      const rect = vsCodeChevronRef.current.getBoundingClientRect()
      setVsCodeDropdownPos({ top: rect.bottom + 4, left: rect.left })
    }
    setVsCodeDropdownOpen((v) => !v)
  }

  async function launchInApp(appType: string): Promise<void> {
    setVsCodeDropdownOpen(false)
    try {
      await window.pathly.shell.openInApp(projectPath, appType)
    } catch { /* surface errors silently */ }
  }

  async function launchTerminalWithKind(cmd: string | undefined, label: string): Promise<void> {
    setTerminalDropdownOpen(false)
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

  function openTerminalDropdown(): void {
    if (terminalChevronRef.current) {
      const rect = terminalChevronRef.current.getBoundingClientRect()
      setTerminalDropdownPos({ top: rect.bottom + 4, right: window.innerWidth - rect.right })
    }
    setTerminalDropdownOpen((v) => !v)
  }

  const badgeLabel = monitorSource === 'sse' ? 'SSE live' : 'File watch'
  const badge = (
    <Tooltip label={badgeLabel} placement="bottom">
      <span className={monitorSource === 'sse' ? styles.badgeLive : styles.badgeWatch}>●</span>
    </Tooltip>
  )

  return (
    <>
      <div className={styles.bar}>
        <IconButton onClick={() => setSidebarCollapsed(!sidebarCollapsed)} title={sidebarCollapsed ? 'Open sidebar' : 'Close sidebar'} placement="bottom">
          <Menu size={15} />
        </IconButton>

        <Tooltip label="Back to projects" placement="bottom">
          <button className={styles.backBtn} onClick={() => setProjectPath('')}>Projects</button>
        </Tooltip>

        <div className={styles.center}>
          <div className={styles.selectWrap}>
            <select
              className={styles.topicSelect}
              aria-label="Active topic"
              value={activeTopic?.startsWith('.archive/') ? '' : (activeTopic ?? '')}
              onChange={(e) => { setActiveTopic(e.target.value || null) }}
            >
              <option value="">— active topic —</option>
              {activeTopics.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          {projectPath && (
            <div className={styles.vsCodeSplit}>
              <Tooltip label="Open in VS Code" placement="bottom">
                <button
                  className={styles.vsCodeSplitMain}
                  onClick={() => void window.pathly.shell.openVsCode(projectPath)}
                  aria-label="Open in VS Code"
                >
                  <VsCodeIcon size={14} style={{ color: '#007ACC' }} />
                </button>
              </Tooltip>
              <div className={styles.vsCodeSplitDivider} />
              <button
                ref={vsCodeChevronRef}
                className={styles.vsCodeSplitChevron}
                onClick={openVsCodeDropdown}
                aria-label="Open project in…"
              >
                <ChevronDown size={10} />
              </button>
            </div>
          )}
          {vsCodeDropdownOpen && vsCodeDropdownPos && createPortal(
            <div
              ref={vsCodeDropdownRef}
              className={styles.vsCodeDropdown}
              style={{ position: 'fixed', top: vsCodeDropdownPos.top, left: vsCodeDropdownPos.left }}
            >
              <div className={styles.vsCodeDropdownLabel}>Open project in…</div>
              <div className={styles.vsCodeDropdownDivider} />
              <button className={styles.vsCodeDropdownItem} onClick={() => void launchInApp('vscode')}>
                <VsCodeIcon size={15} style={{ color: '#007ACC' }} />
                VS Code
              </button>
              <button className={styles.vsCodeDropdownItem} onClick={() => void launchInApp('explorer')}>
                <FileExplorerIcon size={15} />
                File Explorer
              </button>
              <button className={styles.vsCodeDropdownItem} onClick={() => void launchInApp('terminal')}>
                <WindowsTerminalIcon size={15} />
                Terminal
              </button>
              <button className={styles.vsCodeDropdownItem} onClick={() => void launchInApp('gitbash')}>
                <GitBashIcon size={15} />
                Git Bash
              </button>
              <button className={styles.vsCodeDropdownItem} onClick={() => void launchInApp('wsl')}>
                <WslIcon size={15} />
                WSL
              </button>
              <button className={styles.vsCodeDropdownItem} onClick={() => void launchInApp('pycharm')}>
                <PyCharmIcon size={15} />
                PyCharm
              </button>
            </div>,
            document.body
          )}
          {projectPath && (
            <IconButton
              onClick={() => void window.pathly.shell.openWindow(projectPath)}
              title="New Pathly window"
              description="Open multiple projects simultaneously in separate windows"
              placement="bottom"
            >
              <Copy size={14} />
            </IconButton>
          )}
          <div style={{ display: 'flex', gap: 4, marginLeft: 12, flexShrink: 0 }}>
            <Tooltip label="Flow canvas" shortcut="Ctrl+1" placement="bottom">
              <button
                className={`${styles.navBtn} ${activePanel === 'flow' ? styles.navBtnActive : ''}`}
                onClick={() => setActivePanel('flow')}
              >
                <LayoutGrid size={13} />
                Canvas
              </button>
            </Tooltip>
            <Tooltip label="Plan board" shortcut="Ctrl+2" placement="bottom">
              <button
                className={`${styles.navBtn} ${activePanel === 'plan' ? styles.navBtnActive : ''}`}
                onClick={() => setActivePanel('plan')}
              >
                <List size={13} />
                Plan
              </button>
            </Tooltip>
            <Tooltip label="Live monitor" shortcut="Ctrl+3" placement="bottom">
              <button
                className={`${styles.navBtn} ${activePanel === 'monitor' ? styles.navBtnActive : ''}`}
                onClick={() => setActivePanel('monitor')}
              >
                <Activity size={13} />
                Monitor
              </button>
            </Tooltip>
          </div>
        </div>

        <div className={styles.right}>
          {badge}
          <IconButton
            onClick={toggleChat}
            title="HQ"
            description="Command center above your AI model orchestrators"
            placement="bottom"
          >
            <Brain size={14} style={{ color: chatOpen ? 'var(--theme-accent)' : undefined }} />
          </IconButton>
          <IconButton
            onClick={() => setTheme(isLightPalette(theme) ? preferredDark : preferredLight)}
            title={isLightPalette(theme) ? `Switch to dark (${preferredDark})` : `Switch to light (${preferredLight})`}
          >
            {isLightPalette(theme) ? <Moon size={14} /> : <Sun size={14} />}
          </IconButton>
          <div className={styles.terminalSplit}>
            <IconButton onClick={() => toggleTerminal()} title="Toggle terminal" shortcut="Ctrl+`">
              <Terminal size={14} />
            </IconButton>
            <div className={styles.terminalSplitDivider} />
            <button
              ref={terminalChevronRef}
              className={styles.terminalSplitChevron}
              onClick={openTerminalDropdown}
              aria-label="Open terminal launcher"
            >
              <ChevronDown size={10} />
            </button>
          </div>
          {terminalDropdownOpen && terminalDropdownPos && createPortal(
            <div
              ref={terminalDropdownRef}
              className={styles.terminalDropdown}
              style={{ position: 'fixed', top: terminalDropdownPos.top, right: terminalDropdownPos.right }}
            >
              <button className={styles.terminalDropdownItem} onClick={() => void launchTerminalWithKind(undefined, `Shell ${tabs.length + 1}`)}>
                + Shell
              </button>
              <div className={styles.terminalDropdownDivider} />
              <button className={styles.terminalDropdownItem} onClick={() => void launchTerminalWithKind('claude', 'Claude')}>
                <ClaudeIcon size={13} />
                Claude Code
              </button>
              <button className={styles.terminalDropdownItem} onClick={() => void launchTerminalWithKind('codex', 'Codex')}>
                <CodexIcon size={13} />
                Codex
              </button>
            </div>,
            document.body
          )}
          <Tooltip label="Push hooks to server" placement="bottom">
            <button className={styles.publishBtn} onClick={() => void handlePublish()} disabled={publishing}>
              {publishing ? '…' : 'Publish'}
            </button>
          </Tooltip>
        </div>
      </div>

      {showLog && (
        <div className={styles.logPanel}>
          <div className={styles.logHeader}>
            <span>Publish output</span>
            <IconButton onClick={() => setShowLog(false)} title="Close publish log">
              <X size={12} />
            </IconButton>
          </div>
          <div className={styles.logBody}>
            {publishLog.map((line, i) => <div key={i} className={styles.logLine}>{line}</div>)}
            <div ref={logEndRef} />
          </div>
        </div>
      )}
    </>
  )
}
