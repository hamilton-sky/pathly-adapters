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

    // Clipboard: capture selection before xterm clears it on right-click
    const container = containerRef.current!
    let savedSel = ''
    const clipWrite = (text: string): void => { void window.pathly?.clipboard?.write(text) }
    const clipRead = (cb: (t: string) => void): void => {
      void window.pathly?.clipboard?.read().then(cb)
    }

    xterm.attachCustomKeyEventHandler((event: KeyboardEvent) => {
      if (event.type !== 'keydown') return true
      if (event.ctrlKey && !event.shiftKey && event.key === 'c') {
        const sel = xterm.getSelection(); if (sel) { clipWrite(sel); return false } return true
      }
      if (event.ctrlKey && !event.shiftKey && event.key === 'v') {
        clipRead((text) => window.pathly?.terminal?.write(tabId, text)); return false
      }
      if (event.ctrlKey && event.shiftKey && event.key === 'C') {
        const sel = xterm.getSelection(); if (sel) clipWrite(sel); return false
      }
      if (event.ctrlKey && event.shiftKey && event.key === 'V') {
        clipRead((text) => window.pathly?.terminal?.write(tabId, text)); return false
      }
      return true
    })

    const onMouseDown = (e: MouseEvent): void => { if (e.button === 2) savedSel = xterm.getSelection() }
    const onContextMenu = (e: MouseEvent): void => {
      e.preventDefault()
      const sel = savedSel || xterm.getSelection(); savedSel = ''
      if (sel) clipWrite(sel)
      else clipRead((text) => window.pathly?.terminal?.write(tabId, text))
    }
    const onDragEnter = (e: DragEvent): void => { e.preventDefault(); e.stopPropagation() }
    const onDragOver = (e: DragEvent): void => { e.preventDefault(); e.stopPropagation(); if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy' }
    const onDrop = (e: DragEvent): void => {
      e.preventDefault(); e.stopPropagation()
      if (e.dataTransfer?.files.length) {
        const paths = Array.from(e.dataTransfer.files).map((f) => (f as File & { path?: string }).path ?? f.name).join(' ')
        if (paths) window.pathly?.terminal?.write(tabId, paths)
        return
      }
      const text = e.dataTransfer?.getData('text/plain') ?? ''
      if (text) window.pathly?.terminal?.write(tabId, text)
    }
    container.addEventListener('mousedown', onMouseDown)
    container.addEventListener('contextmenu', onContextMenu)
    container.addEventListener('dragenter', onDragEnter, true)
    container.addEventListener('dragover', onDragOver, true)
    container.addEventListener('drop', onDrop, true)

    return () => {
      removeOnData?.()
      removeOnExit?.()
      disposeOnKey.dispose()
      window.removeEventListener('resize', onResize)
      container.removeEventListener('mousedown', onMouseDown)
      container.removeEventListener('contextmenu', onContextMenu)
      container.removeEventListener('dragenter', onDragEnter, true)
      container.removeEventListener('dragover', onDragOver, true)
      container.removeEventListener('drop', onDrop, true)
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
