import { useEffect, useRef } from 'react'
import { Terminal as XTerm } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'

interface Props {
  tabId: string
  label: string
}

export function PopoutTerminal({ tabId, label }: Props): JSX.Element {
  const containerRef = useRef<HTMLDivElement>(null)
  const xtermRef = useRef<XTerm | null>(null)
  const fitAddonRef = useRef<FitAddon | null>(null)

  useEffect(() => {
    if (!containerRef.current) return

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
    xterm.open(containerRef.current)
    xtermRef.current = xterm
    fitAddonRef.current = fitAddon

    setTimeout(() => {
      try {
        fitAddon.fit()
        void window.pathly?.terminal?.resize(tabId, xterm.cols, xterm.rows)
      } catch { /* ignore */ }
    }, 100)

    const removeOnData = window.pathly?.terminal?.onData(tabId, (data) => {
      xterm.write(data)
    })

    const disposeOnKey = xterm.onData((data) => {
      window.pathly?.terminal?.write(tabId, data)
    })

    const removeOnExit = window.pathly?.terminal?.onExit((_id) => {
      xterm.write('\r\n[process exited]\r\n')
    })

    const onResize = (): void => {
      try {
        fitAddon.fit()
        void window.pathly?.terminal?.resize(tabId, xterm.cols, xterm.rows)
      } catch { /* ignore */ }
    }
    window.addEventListener('resize', onResize)

    return () => {
      removeOnData?.()
      removeOnExit?.()
      disposeOnKey.dispose()
      window.removeEventListener('resize', onResize)
      xterm.dispose()
    }
  }, [tabId])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#1e1e2e' }}>
      <div style={{
        height: '32px',
        background: '#181825',
        borderBottom: '1px solid #313244',
        display: 'flex',
        alignItems: 'center',
        paddingLeft: '12px',
        fontSize: '12px',
        color: '#cdd6f4',
        fontFamily: 'system-ui',
        flexShrink: 0,
      }}>
        {label}
      </div>
      <div ref={containerRef} style={{ flex: 1, overflow: 'hidden' }} />
    </div>
  )
}
