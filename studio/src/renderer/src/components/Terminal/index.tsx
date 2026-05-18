import { useEffect, useRef, useState, useCallback } from 'react'
import { Terminal as XTerm } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { useTerminalStore } from '../../store/terminalStore'
import { useStore } from '../../store'
import '@xterm/xterm/css/xterm.css'

interface TabInstance {
  xterm: XTerm
  fitAddon: FitAddon
  container: HTMLDivElement | null
}

const TAB_INSTANCES = new Map<string, TabInstance>()

function createTabId(): string {
  return `tab-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
}

interface TerminalTabViewProps {
  tabId: string
  active: boolean
}

function TerminalTabView({ tabId, active }: TerminalTabViewProps): JSX.Element {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!TAB_INSTANCES.has(tabId)) {
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
      TAB_INSTANCES.set(tabId, { xterm, fitAddon, container: null })
    }

    const instance = TAB_INSTANCES.get(tabId)!

    if (containerRef.current && instance.container !== containerRef.current) {
      instance.xterm.open(containerRef.current)
      instance.container = containerRef.current
      try { instance.fitAddon.fit() } catch { /* ignore */ }
    }
  }, [tabId])

  useEffect(() => {
    const instance = TAB_INSTANCES.get(tabId)
    if (instance && active) {
      setTimeout(() => {
        try { instance.fitAddon.fit() } catch { /* ignore */ }
      }, 0)
    }
  }, [tabId, active])

  useEffect(() => {
    const instance = TAB_INSTANCES.get(tabId)
    if (!instance) return

    const removeListener = (window as unknown as { pathly: { terminal: { onData(tabId: string, cb: (data: string) => void): () => void } } }).pathly.terminal.onData(tabId, (data) => {
      instance.xterm.write(data)
    })

    const disposeOnData = instance.xterm.onData((data: string) => {
      ;(window as unknown as { pathly: { terminal: { write(tabId: string, data: string): Promise<void> } } }).pathly.terminal.write(tabId, data).catch(() => {})
    })

    return () => {
      removeListener()
      disposeOnData.dispose()
    }
  }, [tabId])

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

const pathlyTerminal = (): {
  spawn(tabId: string, cwd: string): Promise<void>
  kill(tabId: string): Promise<void>
} => {
  return (window as unknown as { pathly: { terminal: { spawn(tabId: string, cwd: string): Promise<void>; kill(tabId: string): Promise<void> } } }).pathly.terminal
}

export function Terminal(): JSX.Element | null {
  const { open, tabs, activeTabId, toggle, addTab, closeTab, setActiveTab } = useTerminalStore()
  const projectPath = useStore((s) => s.projectPath)
  const [panelHeight, setPanelHeight] = useState(240)
  const dragStartRef = useRef<{ y: number; h: number } | null>(null)

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
        TAB_INSTANCES.forEach((inst) => {
          try { inst.fitAddon.fit() } catch { /* ignore */ }
        })
      }, 50)
    }
  }, [open, panelHeight])

  const handleAddTab = async (): Promise<void> => {
    const id = createTabId()
    const label = `Shell ${tabs.length + 1}`
    addTab(id, label)
    try {
      await pathlyTerminal().spawn(id, projectPath)
    } catch (err) {
      const instance = TAB_INSTANCES.get(id)
      if (instance) {
        instance.xterm.write(`\r\nError: could not start terminal — ${String(err)}\r\n`)
      }
    }
  }

  const handleCloseTab = async (id: string, e: React.MouseEvent): Promise<void> => {
    e.stopPropagation()
    try {
      await pathlyTerminal().kill(id)
    } catch { /* PTY may already be dead */ }
    const instance = TAB_INSTANCES.get(id)
    if (instance) {
      instance.xterm.dispose()
      TAB_INSTANCES.delete(id)
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
      const newH = Math.max(80, dragStartRef.current.h + delta)
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

  if (!open) return null

  return (
    <div
      style={{
        height: `${panelHeight}px`,
        display: 'flex',
        flexDirection: 'column',
        background: '#1e1e2e',
        borderTop: '1px solid #313244',
        flexShrink: 0,
        position: 'relative',
      }}
    >
      {/* drag handle */}
      <div
        onMouseDown={onDragMouseDown}
        style={{
          height: '5px',
          cursor: 'ns-resize',
          background: '#313244',
          flexShrink: 0,
        }}
      />

      {/* tab bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          height: '32px',
          background: '#181825',
          borderBottom: '1px solid #313244',
          flexShrink: 0,
          paddingLeft: '4px',
          overflow: 'hidden',
        }}
      >
        {tabs.map((tab) => (
          <div
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '0 10px',
              height: '100%',
              cursor: 'pointer',
              fontSize: '12px',
              color: tab.id === activeTabId ? '#cdd6f4' : '#6c7086',
              background: tab.id === activeTabId ? '#1e1e2e' : 'transparent',
              borderRight: '1px solid #313244',
              userSelect: 'none',
              whiteSpace: 'nowrap',
            }}
          >
            {tab.label}
            <span
              onClick={(e) => void handleCloseTab(tab.id, e)}
              style={{
                fontSize: '10px',
                color: '#6c7086',
                lineHeight: 1,
                padding: '1px 2px',
                borderRadius: '2px',
                cursor: 'pointer',
              }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = '#f38ba8' }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.color = '#6c7086' }}
            >
              ✕
            </span>
          </div>
        ))}
        <button
          onClick={() => void handleAddTab()}
          style={{
            background: 'none',
            border: 'none',
            color: '#6c7086',
            cursor: 'pointer',
            fontSize: '16px',
            padding: '0 10px',
            height: '100%',
            lineHeight: 1,
            flexShrink: 0,
          }}
          title="New terminal"
        >
          +
        </button>
      </div>

      {/* xterm content area */}
      <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
        {tabs.length === 0 && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#6c7086',
              fontSize: '13px',
            }}
          >
            Press + to open a terminal
          </div>
        )}
        {tabs.map((tab) => (
          <TerminalTabView
            key={tab.id}
            tabId={tab.id}
            active={tab.id === activeTabId}
          />
        ))}
      </div>
    </div>
  )
}
