import { useEffect, useRef, useState, useCallback } from 'react'
import { Terminal as XTerm } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { useTerminalStore } from '../../store/terminalStore'
import { useStore } from '../../store'
import { useTheme } from '../../useTheme'
import type { Theme } from '../../theme'
import '@xterm/xterm/css/xterm.css'

interface TabInstance {
  xterm: XTerm
  fitAddon: FitAddon
  container: HTMLDivElement | null
}

function makeStyles(t: Theme): Record<string, React.CSSProperties> {
  return {
    panel: {
      display: 'flex',
      flexDirection: 'column',
      background: t.bgBase,
      borderTop: `1px solid ${t.bgSurface1}`,
      flexShrink: 0,
      position: 'relative',
    },
    dragHandle: {
      height: '5px',
      cursor: 'ns-resize',
      background: t.bgSurface1,
      flexShrink: 0,
    },
    toolbar: {
      display: 'flex',
      alignItems: 'center',
      height: '32px',
      background: t.bgMantle,
      borderBottom: `1px solid ${t.bgSurface1}`,
      flexShrink: 0,
      paddingLeft: '4px',
      gap: '2px',
    },
    paneTabBar: {
      display: 'flex',
      alignItems: 'center',
      height: '28px',
      background: t.bgMantle,
      borderBottom: `1px solid ${t.bgSurface0}`,
      paddingLeft: '4px',
      overflow: 'hidden',
      flexShrink: 0,
    },
    tabActive: {
      display: 'flex',
      alignItems: 'center',
      gap: '6px',
      padding: '0 8px',
      height: '100%',
      cursor: 'pointer',
      fontSize: '12px',
      color: t.textPrimary,
      background: t.bgBase,
      borderRight: `1px solid ${t.bgSurface1}`,
      userSelect: 'none',
      whiteSpace: 'nowrap',
    },
    tabInactive: {
      display: 'flex',
      alignItems: 'center',
      gap: '6px',
      padding: '0 8px',
      height: '100%',
      cursor: 'pointer',
      fontSize: '12px',
      color: t.textMuted,
      background: 'transparent',
      borderRight: `1px solid ${t.bgSurface1}`,
      userSelect: 'none',
      whiteSpace: 'nowrap',
    },
    closeBtn: {
      fontSize: '10px',
      color: t.textMuted,
      lineHeight: 1,
      padding: '1px 2px',
      borderRadius: '2px',
      cursor: 'pointer',
    },
    iconBtn: {
      background: 'none',
      border: 'none',
      color: t.textMuted,
      cursor: 'pointer',
      fontSize: '14px',
      padding: '0 7px',
      height: '100%',
      lineHeight: 1,
      flexShrink: 0,
    },
    splitArea: {
      flex: 1,
      display: 'flex',
      overflow: 'hidden',
    },
    pane: {
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      flex: 1,
    },
    splitDivider: {
      width: '4px',
      cursor: 'col-resize',
      background: t.bgSurface1,
      flexShrink: 0,
    },
    contentArea: {
      flex: 1,
      overflow: 'hidden',
      position: 'relative',
    },
    emptyHint: {
      position: 'absolute',
      inset: 0,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: t.textMuted,
      fontSize: '13px',
    },
    labelInput: {
      background: 'transparent',
      border: 'none',
      borderBottom: `1px solid ${t.accent}`,
      color: t.textPrimary,
      fontSize: '12px',
      outline: 'none',
      width: '80px',
      padding: '0 2px',
    },
  }
}

interface TerminalTabViewProps {
  tabId: string
  active: boolean
  tabInstancesRef: React.MutableRefObject<Map<string, TabInstance>>
}

function TerminalTabView({ tabId, active, tabInstancesRef }: TerminalTabViewProps): JSX.Element {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!tabInstancesRef.current.has(tabId)) {
      const xterm = new XTerm({
        theme: {
          background: '#1e1e2e',
          foreground: '#cdd6f4',
          cursor: '#f5c2e7',
          selectionBackground: '#45475a',
        },
        fontSize: 13,
        fontFamily: "'Fira Mono', 'Cascadia Code', monospace",
        cursorBlink: true,
      })
      const fitAddon = new FitAddon()
      xterm.loadAddon(fitAddon)
      tabInstancesRef.current.set(tabId, { xterm, fitAddon, container: null })
    }

    const instance = tabInstancesRef.current.get(tabId)!

    if (containerRef.current && instance.container !== containerRef.current) {
      if (instance.xterm.element) {
        // xterm already opened — move its DOM to the new container instead of calling open() again
        containerRef.current.appendChild(instance.xterm.element)
      } else {
        instance.xterm.open(containerRef.current)
      }
      instance.container = containerRef.current

      setTimeout(() => {
        const inst = tabInstancesRef.current.get(tabId)
        if (inst) {
          try {
            inst.fitAddon.fit()
            const { cols, rows } = inst.xterm
            void window.pathly?.terminal?.resize(tabId, cols, rows)
          } catch { /* ignore */ }
        }
      }, 150)
    }
  }, [tabId, tabInstancesRef])

  useEffect(() => {
    const instance = tabInstancesRef.current.get(tabId)
    if (instance && active) {
      setTimeout(() => {
        try {
          instance.fitAddon.fit()
          const { cols, rows } = instance.xterm
          void window.pathly?.terminal?.resize(tabId, cols, rows)
        } catch { /* ignore */ }
      }, 100)
    }
  }, [tabId, active, tabInstancesRef])

  useEffect(() => {
    const instance = tabInstancesRef.current.get(tabId)
    if (!instance) return
    const pathlyApi = window.pathly?.terminal
    if (!pathlyApi) return
    const removeListener = pathlyApi.onData(tabId, (data) => {
      instance.xterm.write(data)
    })
    const disposeOnData = instance.xterm.onData((data: string) => {
      pathlyApi.write(tabId, data)
    })
    return () => {
      removeListener()
      disposeOnData.dispose()
    }
  }, [tabId, tabInstancesRef])

  useEffect(() => {
    const instance = tabInstancesRef.current.get(tabId)
    if (!instance) return

    const clipWrite = (text: string): void => {
      void window.pathly?.clipboard?.write(text)
    }
    const clipRead = (cb: (text: string) => void): void => {
      void window.pathly?.clipboard?.read().then(cb)
    }

    instance.xterm.attachCustomKeyEventHandler((event: KeyboardEvent) => {
      if (event.type !== 'keydown') return true
      // Ctrl+Shift+C → copy selection
      if (event.ctrlKey && event.shiftKey && event.key === 'C') {
        const sel = instance.xterm.getSelection()
        if (sel) clipWrite(sel)
        return false
      }
      // Ctrl+Shift+V → paste from clipboard
      if (event.ctrlKey && event.shiftKey && event.key === 'V') {
        clipRead((text) => void window.pathly?.terminal?.write(tabId, text))
        return false
      }
      return true
    })

    const container = instance.container
    if (!container) return

    // Capture selection on right-mousedown BEFORE xterm clears it on contextmenu
    let savedSel = ''
    const handleMouseDown = (e: MouseEvent): void => {
      if (e.button === 2) savedSel = instance.xterm.getSelection()
    }

    const handleContextMenu = (e: MouseEvent): void => {
      e.preventDefault()
      const sel = savedSel || instance.xterm.getSelection()
      savedSel = ''
      if (sel) {
        clipWrite(sel)
      } else {
        clipRead((text) => void window.pathly?.terminal?.write(tabId, text))
      }
    }

    // Accept text and file-path drops into the terminal
    const handleDragOver = (e: DragEvent): void => {
      e.preventDefault()
      if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy'
    }
    const handleDrop = (e: DragEvent): void => {
      e.preventDefault()
      if (e.dataTransfer?.files.length) {
        const paths = Array.from(e.dataTransfer.files)
          .map((f) => (f as File & { path?: string }).path ?? f.name)
          .join(' ')
        if (paths) void window.pathly?.terminal?.write(tabId, paths)
        return
      }
      const text = e.dataTransfer?.getData('text/plain') ?? ''
      if (text) void window.pathly?.terminal?.write(tabId, text)
    }

    container.addEventListener('mousedown', handleMouseDown)
    container.addEventListener('contextmenu', handleContextMenu)
    container.addEventListener('dragover', handleDragOver)
    container.addEventListener('drop', handleDrop)
    return () => {
      container.removeEventListener('mousedown', handleMouseDown)
      container.removeEventListener('contextmenu', handleContextMenu)
      container.removeEventListener('dragover', handleDragOver)
      container.removeEventListener('drop', handleDrop)
    }
  }, [tabId, tabInstancesRef])

  return (
    <div
      ref={containerRef}
      style={{
        display: active ? 'block' : 'none',
        width: '100%',
        height: '100%',
        overflow: 'hidden',
      }}
    />
  )
}

interface PaneTabBarProps {
  pane: 'left' | 'right'
  tabs: import('../../store/terminalStore').TerminalTab[]
  activeTabId: string | null
  theme: Theme
  styles: Record<string, React.CSSProperties>
  onSelectTab: (id: string) => void
  onCloseTab: (id: string, e: React.MouseEvent) => void
  onAddTab: (pane: 'left' | 'right') => void
  onLaunch: (cmd: string | undefined, label: string, pane: 'left' | 'right') => void
  onPopout: (id: string) => void
  onRenameTab: (id: string, label: string) => void
}

function PaneTabBar({
  pane, tabs, activeTabId, theme, styles,
  onSelectTab, onCloseTab, onAddTab, onLaunch, onPopout, onRenameTab,
}: PaneTabBarProps): JSX.Element {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')

  const startEdit = (id: string, currentLabel: string, e: React.MouseEvent): void => {
    e.stopPropagation()
    setEditingId(id)
    setEditValue(currentLabel)
  }

  const commitEdit = (): void => {
    if (editingId && editValue.trim()) {
      onRenameTab(editingId, editValue.trim())
    }
    setEditingId(null)
  }

  const cancelEdit = (): void => setEditingId(null)

  return (
    <div style={styles.paneTabBar}>
      {tabs.map((tab) => (
        <div
          key={tab.id}
          onClick={() => onSelectTab(tab.id)}
          style={tab.id === activeTabId ? styles.tabActive : styles.tabInactive}
        >
          {editingId === tab.id ? (
            <input
              autoFocus
              style={styles.labelInput}
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onBlur={commitEdit}
              onKeyDown={(e) => {
                if (e.key === 'Enter') commitEdit()
                if (e.key === 'Escape') cancelEdit()
                e.stopPropagation()
              }}
              onClick={(e) => e.stopPropagation()}
            />
          ) : (
            <span onDoubleClick={(e) => startEdit(tab.id, tab.label, e)}>
              {tab.label}
            </span>
          )}
          {/* Pop-out button — visible on tab hover via CSS-in-JS inline state */}
          <button
            title="Pop out to its own window"
            onClick={(e) => { e.stopPropagation(); onPopout(tab.id) }}
            style={{
              background: 'none',
              border: `1px solid transparent`,
              borderRadius: '3px',
              cursor: 'pointer',
              padding: '1px 4px',
              fontSize: '10px',
              color: theme.textMuted,
              lineHeight: 1,
              marginLeft: '4px',
              flexShrink: 0,
              letterSpacing: '0.5px',
            }}
            onMouseEnter={(e) => {
              const el = e.currentTarget as HTMLElement
              el.style.color = theme.accent
              el.style.borderColor = theme.accent
            }}
            onMouseLeave={(e) => {
              const el = e.currentTarget as HTMLElement
              el.style.color = theme.textMuted
              el.style.borderColor = 'transparent'
            }}
          >
            ⬡ pop
          </button>
          <button
            title="Close tab"
            onClick={(e) => { e.stopPropagation(); onCloseTab(tab.id, e) }}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '1px 4px', fontSize: '11px', color: theme.textMuted, lineHeight: 1, flexShrink: 0 }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = theme.red }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.color = theme.textMuted }}
          >✕</button>
        </div>
      ))}
      <div style={{ display: 'flex', alignItems: 'center', gap: '2px', paddingLeft: '4px' }}>
        <button onClick={() => onAddTab(pane)} style={{ ...styles.iconBtn, fontSize: '11px' }} title="New shell">+ Shell</button>
        <button
          onClick={() => onLaunch('claude', 'Claude', pane)}
          style={{ ...styles.iconBtn, fontSize: '10px', fontWeight: 700, color: theme.accent }}
          title="Launch Claude Code"
        >Claude</button>
        <button
          onClick={() => onLaunch('codex', 'Codex', pane)}
          style={{ ...styles.iconBtn, fontSize: '10px', fontWeight: 700, color: theme.green }}
          title="Launch Codex"
        >Codex</button>
      </div>
    </div>
  )
}

export function Terminal(): JSX.Element {
  const {
    open, tabs, activeTabIdLeft, activeTabIdRight, splitEnabled,
    toggle, addTab, closeTab, setActiveTab, renameTab, toggleSplit,
  } = useTerminalStore()
  const projectPath = useStore((s) => s.projectPath)
  const theme = useTheme()
  const styles = makeStyles(theme)
  const [panelHeight, setPanelHeight] = useState(260)
  const [splitRatio, setSplitRatio] = useState(0.5)
  const panelRef = useRef<HTMLDivElement>(null)
  const vDragRef = useRef<{ x: number; ratio: number } | null>(null)
  const dragStartRef = useRef<{ y: number; h: number } | null>(null)
  const tabInstancesRef = useRef(new Map<string, TabInstance>())

  const leftTabs = tabs.filter((t) => t.pane === 'left')
  const rightTabs = tabs.filter((t) => t.pane === 'right')

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.ctrlKey && e.key === '`') { e.preventDefault(); toggle() }
  }, [toggle])

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  useEffect(() => {
    if (open) {
      setTimeout(() => {
        tabInstancesRef.current.forEach((inst, tid) => {
          try {
            inst.fitAddon.fit()
            const { cols, rows } = inst.xterm
            void window.pathly?.terminal?.resize(tid, cols, rows)
          } catch { /* ignore */ }
        })
      }, 50)
    }
  }, [open, panelHeight, splitEnabled, splitRatio])

  useEffect(() => {
    const api = window.pathly?.terminal
    if (!api) return
    return api.onExit((tabId) => {
      const instance = tabInstancesRef.current.get(tabId)
      if (instance) instance.xterm.write('\r\n[process exited]\r\n')
    })
  }, [])

  const handleLaunch = async (command: string | undefined, label: string, pane: 'left' | 'right' = 'left'): Promise<void> => {
    if (!open) toggle()
    const id = crypto.randomUUID()
    addTab(id, label, pane)
    try {
      await window.pathly?.terminal?.spawn(id, projectPath, command)
    } catch (err) {
      const instance = tabInstancesRef.current.get(id)
      if (instance) instance.xterm.write(`\r\nError: could not start terminal — ${String(err)}\r\n`)
    }
  }

  const handleCloseTab = async (id: string, e: React.MouseEvent): Promise<void> => {
    e.stopPropagation()
    try { await window.pathly?.terminal?.kill(id) } catch { /* PTY may already be dead */ }
    const instance = tabInstancesRef.current.get(id)
    if (instance) { instance.xterm.dispose(); tabInstancesRef.current.delete(id) }
    closeTab(id)
  }

  const handlePopout = async (id: string): Promise<void> => {
    const tab = tabs.find((t) => t.id === id)
    if (!tab) return
    try {
      await window.pathly?.terminal?.popout(id, tab.label)
    } catch (err) {
      console.error('popout failed', err)
      return
    }
    // Remove from this window — PTY now belongs to popup
    const instance = tabInstancesRef.current.get(id)
    if (instance) { instance.xterm.dispose(); tabInstancesRef.current.delete(id) }
    closeTab(id)
  }

  const handleToggleSplit = (): void => {
    toggleSplit()
  }

  // Horizontal drag (panel height)
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
        const relX = e.clientX - rect.left
        const ratio = Math.min(0.85, Math.max(0.15, relX / rect.width))
        setSplitRatio(ratio)
      }
    }
    const onMouseUp = (): void => {
      dragStartRef.current = null
      vDragRef.current = null
    }
    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
    return () => {
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
    }
  }, [])

  const renderPane = (pane: 'left' | 'right', paneTabs: typeof tabs, activeId: string | null): JSX.Element => (
    <div style={styles.pane}>
      <PaneTabBar
        pane={pane}
        tabs={paneTabs}
        activeTabId={activeId}
        theme={theme}
        styles={styles}
        onSelectTab={setActiveTab}
        onCloseTab={(id, e) => void handleCloseTab(id, e)}
        onAddTab={(p) => void handleLaunch(undefined, `Shell ${tabs.length + 1}`, p)}
        onLaunch={(cmd, label, p) => void handleLaunch(cmd, label, p)}
        onPopout={(id) => void handlePopout(id)}
        onRenameTab={renameTab}
      />
      <div style={styles.contentArea}>
        {paneTabs.length === 0 && (
          <div style={styles.emptyHint}>Press + to open a terminal</div>
        )}
        {paneTabs.map((tab) => (
          <TerminalTabView
            key={tab.id}
            tabId={tab.id}
            active={tab.id === activeId}
            tabInstancesRef={tabInstancesRef}
          />
        ))}
      </div>
    </div>
  )

  return (
    <div ref={panelRef} style={{ ...styles.panel, height: `${panelHeight}px`, display: open ? 'flex' : 'none' }}>
      <div onMouseDown={onDragMouseDown} style={styles.dragHandle} />

      {/* Toolbar row — tabs on left, action buttons on right */}
      {!splitEnabled && (
        <div style={{ ...styles.toolbar, justifyContent: 'space-between' }}>
          <PaneTabBar
            pane="left"
            tabs={leftTabs}
            activeTabId={activeTabIdLeft}
            theme={theme}
            styles={{ ...styles, paneTabBar: { display: 'flex', alignItems: 'center', height: '100%', flex: 1, overflow: 'hidden', gap: '2px', paddingLeft: '4px' } }}
            onSelectTab={setActiveTab}
            onCloseTab={(id, e) => void handleCloseTab(id, e)}
            onAddTab={() => void handleLaunch(undefined, `Shell ${tabs.length + 1}`, 'left')}
            onLaunch={(cmd, label) => void handleLaunch(cmd, label, 'left')}
            onPopout={(id) => void handlePopout(id)}
            onRenameTab={renameTab}
          />
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', paddingRight: '6px', flexShrink: 0 }}>
            {/* Split button — only when 2+ tabs exist */}
            {tabs.length >= 2 && (
              <button
                onClick={handleToggleSplit}
                title="Split pane side-by-side"
                style={{ background: 'none', border: `1px solid ${theme.bgSurface1}`, cursor: 'pointer', padding: '3px 6px', borderRadius: '3px', display: 'flex', alignItems: 'center' }}
              >
                <span style={{ display: 'flex', gap: '3px', alignItems: 'center' }}>
                  <span style={{ width: '7px', height: '13px', background: theme.textMuted, borderRadius: '1px', display: 'inline-block' }} />
                  <span style={{ width: '7px', height: '13px', background: theme.textMuted, borderRadius: '1px', display: 'inline-block' }} />
                </span>
              </button>
            )}
            {/* Close panel button */}
            <button
              onClick={toggle}
              title="Close terminal"
              style={{ background: 'none', border: `1px solid ${theme.bgSurface1}`, cursor: 'pointer', padding: '2px 7px', borderRadius: '3px', color: theme.textMuted, fontSize: '14px', lineHeight: 1, display: 'flex', alignItems: 'center' }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = theme.red }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.color = theme.textMuted }}
            >✕</button>
          </div>
        </div>
      )}

      {/* When split, header row shows split (active) + close buttons */}
      {splitEnabled && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', height: '28px', background: theme.bgMantle, borderBottom: `1px solid ${theme.bgSurface1}`, flexShrink: 0, gap: '4px', paddingRight: '6px' }}>
          <button
            onClick={handleToggleSplit}
            title="Close split"
            style={{ background: theme.accent, border: `1px solid ${theme.accent}`, cursor: 'pointer', padding: '3px 6px', borderRadius: '3px', display: 'flex', alignItems: 'center' }}
          >
            <span style={{ display: 'flex', gap: '3px', alignItems: 'center' }}>
              <span style={{ width: '7px', height: '13px', background: theme.bgBase, borderRadius: '1px', display: 'inline-block' }} />
              <span style={{ width: '7px', height: '13px', background: theme.bgBase, borderRadius: '1px', display: 'inline-block' }} />
            </span>
          </button>
          <button
            onClick={toggle}
            title="Close terminal"
            style={{ background: 'none', border: `1px solid ${theme.bgSurface1}`, cursor: 'pointer', padding: '2px 7px', borderRadius: '3px', color: theme.textMuted, fontSize: '14px', lineHeight: 1, display: 'flex', alignItems: 'center' }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = theme.red }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.color = theme.textMuted }}
          >✕</button>
        </div>
      )}

      {/* Content */}
      {splitEnabled ? (
        <div style={styles.splitArea}>
          <div style={{ ...styles.pane, flex: splitRatio }}>
            {renderPane('left', leftTabs, activeTabIdLeft)}
          </div>
          <div
            style={styles.splitDivider}
            onMouseDown={(e) => { vDragRef.current = { x: e.clientX, ratio: splitRatio }; e.preventDefault() }}
          />
          <div style={{ ...styles.pane, flex: 1 - splitRatio }}>
            {renderPane('right', rightTabs, activeTabIdRight)}
          </div>
        </div>
      ) : (
        <div style={styles.contentArea}>
          {leftTabs.length === 0 && (
            <div style={styles.emptyHint}>Press + to open a terminal</div>
          )}
          {leftTabs.map((tab) => (
            <TerminalTabView
              key={tab.id}
              tabId={tab.id}
              active={tab.id === activeTabIdLeft}
              tabInstancesRef={tabInstancesRef}
            />
          ))}
        </div>
      )}
    </div>
  )
}
