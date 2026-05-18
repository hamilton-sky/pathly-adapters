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
    tabBar: {
      display: 'flex',
      alignItems: 'center',
      height: '32px',
      background: t.bgMantle,
      borderBottom: `1px solid ${t.bgSurface1}`,
      flexShrink: 0,
      paddingLeft: '4px',
      overflow: 'hidden',
    },
    tabActive: {
      display: 'flex',
      alignItems: 'center',
      gap: '6px',
      padding: '0 10px',
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
      padding: '0 10px',
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
    addBtn: {
      background: 'none',
      border: 'none',
      color: t.textMuted,
      cursor: 'pointer',
      fontSize: '16px',
      padding: '0 10px',
      height: '100%',
      lineHeight: 1,
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
  }
}

function createTabId(): string {
  return crypto.randomUUID()
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
      instance.xterm.open(containerRef.current)
      instance.container = containerRef.current
      try {
        instance.fitAddon.fit()
        const { cols, rows } = instance.xterm
        void window.pathly?.terminal?.resize(tabId, cols, rows)
      } catch { /* ignore */ }

      // Trigger redraw after mount so PowerShell prompt re-renders
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
      }, 0)
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

const pathlyTerminal = (): Window['pathly']['terminal'] | null => {
  return window.pathly?.terminal ?? null
}

export function Terminal(): JSX.Element {
  const { open, tabs, activeTabId, toggle, addTab, closeTab, setActiveTab } = useTerminalStore()
  const projectPath = useStore((s) => s.projectPath)
  const theme = useTheme()
  const styles = makeStyles(theme)
  const [panelHeight, setPanelHeight] = useState(260)
  const dragStartRef = useRef<{ y: number; h: number } | null>(null)
  const tabInstancesRef = useRef(new Map<string, TabInstance>())

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.ctrlKey && e.key === '`') {
      e.preventDefault()
      toggle()
    }
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
  }, [open, panelHeight])

  useEffect(() => {
    const api = pathlyTerminal()
    if (!api) return
    const removeOnExit = api.onExit((tabId) => {
      const instance = tabInstancesRef.current.get(tabId)
      if (instance) {
        instance.xterm.write('\r\n[process exited]\r\n')
      }
    })
    return removeOnExit
  }, [])

  const handleLaunch = async (command: string | undefined, label: string): Promise<void> => {
    const id = crypto.randomUUID()
    addTab(id, label)
    try {
      await window.pathly?.terminal?.spawn(id, projectPath, command)
    } catch (err) {
      const instance = tabInstancesRef.current.get(id)
      if (instance) {
        instance.xterm.write(`\r\nError: could not start terminal — ${String(err)}\r\n`)
      }
    }
  }

  const handleAddTab = (): void => {
    void handleLaunch(undefined, `Shell ${tabs.length + 1}`)
  }

  const handleCloseTab = async (id: string, e: React.MouseEvent): Promise<void> => {
    e.stopPropagation()
    try {
      await pathlyTerminal()?.kill(id)
    } catch { /* PTY may already be dead */ }
    const instance = tabInstancesRef.current.get(id)
    if (instance) {
      instance.xterm.dispose()
      tabInstancesRef.current.delete(id)
    }
    closeTab(id)
  }

  const onDragMouseDown = (e: React.MouseEvent): void => {
    dragStartRef.current = { y: e.clientY, h: panelHeight }
    e.preventDefault()
  }

  useEffect(() => {
    const onMouseMove = (e: MouseEvent): void => {
      if (!dragStartRef.current) return
      const delta = dragStartRef.current.y - e.clientY
      const newH = Math.min(800, Math.max(80, dragStartRef.current.h + delta))
      setPanelHeight(newH)
    }
    const onMouseUp = (): void => { dragStartRef.current = null }
    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
    return () => {
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
    }
  }, [])

  return (
    <div
      style={{
        ...styles.panel,
        height: `${panelHeight}px`,
        display: open ? 'flex' : 'none',
      }}
    >
      {/* drag handle */}
      <div
        onMouseDown={onDragMouseDown}
        style={styles.dragHandle}
      />

      {/* tab bar */}
      <div style={styles.tabBar}>
        {tabs.map((tab) => (
          <div
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={tab.id === activeTabId ? styles.tabActive : styles.tabInactive}
          >
            {tab.label}
            <span
              onClick={(e) => void handleCloseTab(tab.id, e)}
              style={styles.closeBtn}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = theme.red }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.color = theme.textMuted }}
            >
              ✕
            </span>
          </div>
        ))}
        <div style={{ display: 'flex', alignItems: 'center', flexShrink: 0, gap: '2px', paddingRight: '4px' }}>
          <button
            onClick={handleAddTab}
            style={styles.addBtn}
            title="New terminal (PowerShell)"
          >⌨</button>
          <button
            onClick={() => void handleLaunch('claude', 'Claude')}
            style={{ ...styles.addBtn, fontSize: '11px', fontWeight: 700, color: theme.accent }}
            title="Launch Claude Code"
          >◆</button>
          <button
            onClick={() => void handleLaunch('codex', 'Codex')}
            style={{ ...styles.addBtn, fontSize: '11px', fontWeight: 700, color: theme.green }}
            title="Launch Codex"
          >⬡</button>
        </div>
      </div>

      {/* xterm content area */}
      <div style={styles.contentArea}>
        {tabs.length === 0 && (
          <div style={styles.emptyHint}>
            Press + to open a terminal
          </div>
        )}
        {tabs.map((tab) => (
          <TerminalTabView
            key={tab.id}
            tabId={tab.id}
            active={tab.id === activeTabId}
            tabInstancesRef={tabInstancesRef}
          />
        ))}
      </div>
    </div>
  )
}
