import { useEffect, useRef } from 'react'
import { Terminal as XTerm } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import type { TabInstance } from './types'
import { useTheme } from '../../useTheme'
import { darkTheme } from '../../theme'
import type { Theme } from '../../theme'
import styles from './Terminal.module.css'

function xtermThemeFor(t: Theme, isDark: boolean): Record<string, string> {
  if (isDark) {
    return {
      background:            t.bgMantle,
      foreground:            t.textPrimary,
      cursor:                t.accent,
      cursorAccent:          t.bgMantle,
      selectionBackground:   t.bgSurface1,
      selectionForeground:   t.textPrimary,
      black:                 t.bgSurface0,
      red:                   t.red,
      green:                 t.green,
      yellow:                t.yellow,
      blue:                  t.blue,
      magenta:               t.accent,
      cyan:                  '#67e8f9',
      white:                 '#cdd6f4',
      brightBlack:           t.textMuted,
      brightRed:             '#fca5a5',
      brightGreen:           '#86efac',
      brightYellow:          '#fde68a',
      brightBlue:            '#93c5fd',
      brightMagenta:         '#c4b5fd',
      brightCyan:            '#a5f3fc',
      brightWhite:           '#f5f5ff',
    }
  } else {
    return {
      background:            t.bgMantle,
      foreground:            t.textPrimary,
      cursor:                t.accent,
      cursorAccent:          t.bgMantle,
      selectionBackground:   t.bgSurface1,
      selectionForeground:   t.textPrimary,
      black:                 '#1e1e3a',
      red:                   t.red,
      green:                 t.green,
      yellow:                '#b45309',
      blue:                  '#1d4ed8',
      magenta:               t.accent,
      cyan:                  '#0e7490',
      white:                 t.textSecondary,
      brightBlack:           t.textMuted,
      brightRed:             '#ef4444',
      brightGreen:           '#22c55e',
      brightYellow:          t.yellow,
      brightBlue:            t.blue,
      brightMagenta:         '#9333ea',
      brightCyan:            '#06b6d4',
      brightWhite:           '#f5f5ff',
    }
  }
}

interface TerminalTabViewProps {
  tabId: string
  active: boolean
  tabInstancesRef: React.MutableRefObject<Map<string, TabInstance>>
}

export function TerminalTabView({ tabId, active, tabInstancesRef }: TerminalTabViewProps): JSX.Element {
  const containerRef = useRef<HTMLDivElement>(null)
  const t = useTheme()
  const isDark = t === darkTheme

  useEffect(() => {
    if (!tabInstancesRef.current.has(tabId)) {
      const xterm = new XTerm({
        theme: xtermThemeFor(t, isDark) as any,
        fontSize: 14,
        fontFamily: "'Cascadia Code', 'Fira Mono', 'JetBrains Mono', monospace",
        cursorBlink: true,
        cursorStyle: 'bar',
        lineHeight: 1.2,
        scrollback: 5000,
      })
      const fitAddon = new FitAddon()
      xterm.loadAddon(fitAddon)
      tabInstancesRef.current.set(tabId, { xterm, fitAddon, container: null })
    }

    const instance = tabInstancesRef.current.get(tabId)!

    if (containerRef.current && instance.container !== containerRef.current) {
      if (instance.xterm.element) {
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

  // Update xterm theme when Pathly theme changes
  useEffect(() => {
    const instance = tabInstancesRef.current.get(tabId)
    if (instance) {
      instance.xterm.options.theme = xtermThemeFor(t, isDark) as any
    }
  }, [isDark, tabId, tabInstancesRef, t])

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
      if (event.ctrlKey && !event.shiftKey && event.key === 'c') {
        const sel = instance.xterm.getSelection()
        if (sel) { clipWrite(sel); return false }
        return true
      }
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
      if (event.ctrlKey && event.shiftKey && event.key === 'C') {
        const sel = instance.xterm.getSelection()
        if (sel) clipWrite(sel)
        return false
      }
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

    const handleDragEnter = (e: DragEvent): void => { e.preventDefault(); e.stopPropagation() }
    const handleDragOver = (e: DragEvent): void => {
      e.preventDefault(); e.stopPropagation()
      if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy'
    }
    const handleDrop = (e: DragEvent): void => {
      e.preventDefault(); e.stopPropagation()
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
