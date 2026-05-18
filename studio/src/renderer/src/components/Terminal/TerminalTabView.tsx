import { useEffect, useRef } from 'react'
import { Terminal as XTerm } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import type { TabInstance } from './types'
import styles from './Terminal.module.css'

interface TerminalTabViewProps {
  tabId: string
  active: boolean
  tabInstancesRef: React.MutableRefObject<Map<string, TabInstance>>
}

export function TerminalTabView({ tabId, active, tabInstancesRef }: TerminalTabViewProps): JSX.Element {
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
      // Ctrl+C → copy if text selected, else pass through as SIGINT
      if (event.ctrlKey && !event.shiftKey && event.key === 'c') {
        const sel = instance.xterm.getSelection()
        if (sel) { clipWrite(sel); return false }
        return true
      }
      // Ctrl+V → paste from clipboard (image takes priority)
      if (event.ctrlKey && !event.shiftKey && event.key === 'v') {
        void (async () => {
          const imgPath = await window.pathly?.clipboard?.readImagePath()
          if (imgPath) {
            void window.pathly?.terminal?.write(tabId, imgPath)
          } else {
            clipRead((text) => void window.pathly?.terminal?.write(tabId, text))
          }
        })()
        return false
      }
      // Ctrl+Shift+C → copy selection (always, no SIGINT ambiguity)
      if (event.ctrlKey && event.shiftKey && event.key === 'C') {
        const sel = instance.xterm.getSelection()
        if (sel) clipWrite(sel)
        return false
      }
      // Ctrl+Shift+V → paste from clipboard (image takes priority)
      if (event.ctrlKey && event.shiftKey && event.key === 'V') {
        void (async () => {
          const imgPath = await window.pathly?.clipboard?.readImagePath()
          if (imgPath) {
            void window.pathly?.terminal?.write(tabId, imgPath)
          } else {
            clipRead((text) => void window.pathly?.terminal?.write(tabId, text))
          }
        })()
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

    // Accept text and file-path drops into the terminal.
    // Use capture phase so our handlers fire before xterm.js can stopPropagation on its canvas.
    const handleDragEnter = (e: DragEvent): void => {
      e.preventDefault()
      e.stopPropagation()
    }
    const handleDragOver = (e: DragEvent): void => {
      e.preventDefault()
      e.stopPropagation()
      if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy'
    }
    const handleDrop = (e: DragEvent): void => {
      e.preventDefault()
      e.stopPropagation()
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
    container.addEventListener('dragenter', handleDragEnter, true)
    container.addEventListener('dragover', handleDragOver, true)
    container.addEventListener('drop', handleDrop, true)
    return () => {
      container.removeEventListener('mousedown', handleMouseDown)
      container.removeEventListener('contextmenu', handleContextMenu)
      container.removeEventListener('dragenter', handleDragEnter, true)
      container.removeEventListener('dragover', handleDragOver, true)
      container.removeEventListener('drop', handleDrop, true)
    }
  }, [tabId, tabInstancesRef])

  return (
    <div
      ref={containerRef}
      className={active ? styles.tabViewActive : styles.tabViewHidden}
    />
  )
}
