import { useEffect, useRef, useState, useCallback } from 'react'
import { Columns2, Menu, X as XIcon } from 'lucide-react'
import { useTerminalStore } from '../../store/terminalStore'
import { useStore } from '../../store'
import { useTheme } from '../../useTheme'
import { TerminalTabView } from './TerminalTabView'
import { PaneTabBar } from './PaneTabBar'
import { TerminalInstancesRail } from './TerminalInstancesRail'
import { launchTerminal } from '../../lib/launchTerminal'
import * as xtermRegistry from './xtermRegistry'
import styles from './Terminal.module.css'

export function Terminal(): JSX.Element {
  const {
    open, tabs, activeTabIdLeft, activeTabIdRight, splitEnabled, hiddenTabIds,
    toggle, addTab, closeTab, hideTab, setActiveTab, openTab, renameTab, toggleSplit,
  } = useTerminalStore()
  const projectPath = useStore((s) => s.projectPath)
  const theme = useTheme()
  const [panelHeight, setPanelHeight] = useState(180)
  const [splitRatio, setSplitRatio] = useState(0.5)
  const [instancesRailOpen, setInstancesRailOpen] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)
  const vDragRef = useRef<{ x: number; ratio: number } | null>(null)
  const dragStartRef = useRef<{ y: number; h: number } | null>(null)

  const themeVars = {
    '--t-bg': theme.bgBase,
    '--t-surface0': theme.bgSurface0,
    '--t-surface1': theme.bgSurface1,
    '--t-mantle': theme.bgMantle,
    '--t-text': theme.textPrimary,
    '--t-text-muted': theme.textMuted,
    '--t-accent': theme.accent,
    '--t-red': theme.red,
    '--t-green': theme.green,
    '--t-blue': theme.blue,
  } as React.CSSProperties

  const leftTabs = tabs.filter((t) => t.pane === 'left' && !hiddenTabIds[t.id])
  const rightTabs = tabs.filter((t) => t.pane === 'right' && !hiddenTabIds[t.id])

  // Ctrl+` global toggle
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.ctrlKey && e.key === '`') { e.preventDefault(); toggle() }
  }, [toggle])

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  // Focus the correct xterm when the mini-terminal "full terminal" button is clicked
  useEffect(() => {
    const handler = (e: Event): void => {
      const { tabId } = (e as CustomEvent<{ tabId: string }>).detail
      setTimeout(() => xtermRegistry.focus(tabId), 60)
    }
    document.addEventListener('pathly:focus-terminal-tab', handler)
    return () => document.removeEventListener('pathly:focus-terminal-tab', handler)
  }, [])

  // Listen for PTY exit — write an exit marker into the shared xterm
  useEffect(() => {
    const api = window.pathly?.terminal
    if (!api) return
    return api.onExit((tabId) => {
      xtermRegistry.write(tabId, '\r\n[process exited]\r\n')
      useTerminalStore.getState().updateTabStatus(tabId, 'done')
    })
  }, [])

  const handleLaunch = async (command: string | undefined, label: string, pane: 'left' | 'right' = 'left'): Promise<void> => {
    try {
      await launchTerminal({ command, label, pane, projectPath, open, toggle, addTab })
    } catch { /* PTY errors surface in terminal */ }
  }

  const killTab = async (id: string): Promise<void> => {
    try { await window.pathly?.terminal?.kill(id) } catch { /* PTY may already be dead */ }
    xtermRegistry.dispose(id)
    closeTab(id)
  }

  const handleCloseTab = async (id: string, e: React.MouseEvent): Promise<void> => {
    e.stopPropagation()
    await killTab(id)
  }

  const handleHideTab = (id: string, e?: React.MouseEvent): void => {
    e?.stopPropagation()
    hideTab(id)
  }

  const handlePopout = async (id: string): Promise<void> => {
    const tab = tabs.find((t) => t.id === id)
    if (!tab) return
    try {
      await window.pathly?.terminal?.popout(id, tab.label)
    } catch { return }
    // Popout transferred PTY ownership to the new BrowserWindow. The local
    // xterm instance is no longer wired to the PTY; dispose it cleanly so any
    // remaining card mounts don't show a stale buffer.
    xtermRegistry.dispose(id)
    closeTab(id)
  }

  // Panel height drag
  const onDragMouseDown = (e: React.MouseEvent): void => {
    dragStartRef.current = { y: e.clientY, h: panelHeight }
    e.preventDefault()
  }

  useEffect(() => {
    const onMouseMove = (e: MouseEvent): void => {
      if (dragStartRef.current) {
        const delta = dragStartRef.current.y - e.clientY
        setPanelHeight(Math.min(800, Math.max(80, dragStartRef.current.h + delta)))
      }
      if (vDragRef.current && panelRef.current) {
        const rect = panelRef.current.getBoundingClientRect()
        const ratio = Math.min(0.85, Math.max(0.15, (e.clientX - rect.left) / rect.width))
        setSplitRatio(ratio)
      }
    }
    const onMouseUp = (): void => { dragStartRef.current = null; vDragRef.current = null }
    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
    return () => {
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
    }
  }, [])

  const renderPane = (pane: 'left' | 'right', paneTabs: typeof tabs, activeId: string | null): JSX.Element => (
    <div className={styles.pane}>
      <PaneTabBar
        pane={pane}
        tabs={paneTabs}
        activeTabId={activeId}
        onSelectTab={setActiveTab}
        onCloseTab={(id, e) => void handleCloseTab(id, e)}
        onHideTab={handleHideTab}
        onAddTab={(p) => void handleLaunch(undefined, `Shell ${tabs.length + 1}`, p)}
        onLaunch={(cmd, label, p) => void handleLaunch(cmd, label, p)}
        onPopout={(id) => void handlePopout(id)}
        onRenameTab={renameTab}
      />
      <div className={styles.contentArea}>
        {paneTabs.length === 0 && <div className={styles.emptyHint}>Press + to open a terminal</div>}
        {paneTabs.map((tab) => (
          <TerminalTabView key={tab.id} tabId={tab.id} active={tab.id === activeId} open={open} />
        ))}
      </div>
    </div>
  )

  const isEmpty = !splitEnabled && tabs.length === 0
  const effectiveHeight = isEmpty ? 72 : panelHeight

  return (
    <div
      ref={panelRef}
      className={styles.panel}
      style={{ ...themeVars, height: `${effectiveHeight}px`, display: open ? 'flex' : 'none', transition: 'height 150ms ease-out' }}
    >
      <div onMouseDown={onDragMouseDown} className={styles.dragHandle} />

      {!splitEnabled && (
        <div className={styles.toolbar}>
          <PaneTabBar
            pane="left"
            tabs={leftTabs}
            activeTabId={activeTabIdLeft}
            inline
            onSelectTab={setActiveTab}
            onCloseTab={(id, e) => void handleCloseTab(id, e)}
            onHideTab={handleHideTab}
            onAddTab={() => void handleLaunch(undefined, `Shell ${tabs.length + 1}`, 'left')}
            onLaunch={(cmd, label) => void handleLaunch(cmd, label, 'left')}
            onPopout={(id) => void handlePopout(id)}
            onRenameTab={renameTab}
          />
          <div className={styles.toolbarActions}>
            {tabs.length >= 2 && (
              <button className={styles.splitIconBtn} onClick={toggleSplit} title="Split pane side-by-side">
                <Columns2 size={13} />
              </button>
            )}
            {tabs.length > 0 && (
              <button
                className={`${styles.splitIconBtn} ${instancesRailOpen ? styles.splitIconBtnActive : ''}`}
                onClick={() => setInstancesRailOpen((v) => !v)}
                title={instancesRailOpen ? 'Close instances panel' : 'Open instances panel'}
              >
                <Menu size={13} />
              </button>
            )}
            <button className={styles.closePanelBtn} onClick={toggle} title="Close terminal"><XIcon size={13} /></button>
          </div>
        </div>
      )}

      {splitEnabled && (
        <div className={styles.splitHeader}>
          <button className={`${styles.splitIconBtn} ${styles.splitIconBtnActive}`} onClick={toggleSplit} title="Close split">
            <Columns2 size={13} />
          </button>
          {tabs.length > 0 && (
            <button
              className={`${styles.splitIconBtn} ${instancesRailOpen ? styles.splitIconBtnActive : ''}`}
              onClick={() => setInstancesRailOpen((v) => !v)}
              title={instancesRailOpen ? 'Close instances panel' : 'Open instances panel'}
            >
              <Menu size={13} />
            </button>
          )}
          <button className={styles.closePanelBtn} onClick={toggle} title="Close terminal"><XIcon size={13} /></button>
        </div>
      )}

      <div className={styles.terminalBody}>
        <div className={styles.terminalWorkspace}>
          {splitEnabled ? (
            <div className={styles.splitArea}>
              <div className={styles.pane} style={{ flex: splitRatio }}>
                {renderPane('left', leftTabs, activeTabIdLeft)}
              </div>
              <div
                className={styles.splitDivider}
                onMouseDown={(e) => { vDragRef.current = { x: e.clientX, ratio: splitRatio }; e.preventDefault() }}
              />
              <div className={styles.pane} style={{ flex: 1 - splitRatio }}>
                {renderPane('right', rightTabs, activeTabIdRight)}
              </div>
            </div>
          ) : (
            <div className={styles.contentArea}>
              {leftTabs.length === 0 && (
                <div className={styles.emptyHint}>No terminal open.</div>
              )}
              {leftTabs.map((tab) => (
                <TerminalTabView key={tab.id} tabId={tab.id} active={tab.id === activeTabIdLeft} open={open} />
              ))}
            </div>
          )}
        </div>
        {tabs.length > 0 && !instancesRailOpen && (
          <button
            type="button"
            className={styles.instancesRailToggle}
            onClick={() => setInstancesRailOpen(true)}
            title="Open instances panel"
            aria-label="Open instances panel"
          >
            <Menu size={14} />
          </button>
        )}
        {tabs.length > 0 && instancesRailOpen && (
          <TerminalInstancesRail
            tabs={tabs}
            activeTabIds={[activeTabIdLeft, activeTabIdRight]}
            hiddenTabIds={hiddenTabIds}
            splitEnabled={splitEnabled}
            onClosePanel={() => setInstancesRailOpen(false)}
            onOpenTab={openTab}
            onHideTab={handleHideTab}
            onKillTab={(id) => void killTab(id)}
          />
        )}
      </div>
    </div>
  )
}
