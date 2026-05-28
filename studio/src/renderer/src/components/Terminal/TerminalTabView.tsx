import { useEffect, useRef } from 'react'
import * as xtermRegistry from './xtermRegistry'
import styles from './Terminal.module.css'

interface TerminalTabViewProps {
  tabId: string
  active: boolean
  open: boolean
}

/**
 * Hosts the shared xterm instance for `tabId` whenever this tab is the active
 * one in its pane AND the full terminal panel is open. Non-active or non-open
 * states release ownership so the chat-panel MiniTerminalCard can host instead.
 */
export function TerminalTabView({ tabId, active, open }: TerminalTabViewProps): JSX.Element {
  const containerRef = useRef<HTMLDivElement>(null)
  const isHost = active && open

  // Attach / detach the shared xterm based on host state.
  useEffect(() => {
    if (!isHost || !containerRef.current) {
      xtermRegistry.detachFrom(tabId, 'full')
      return
    }
    xtermRegistry.getOrCreate(tabId, { fontSize: 14 })
    xtermRegistry.attachTo(tabId, 'full', containerRef.current, { fontSize: 14 })
    // Two-pass fit: immediate pass catches initial layout; the 150 ms pass
    // accounts for monospace webfont loading delay.
    const t0 = setTimeout(() => xtermRegistry.fit(tabId), 0)
    const t1 = setTimeout(() => {
      xtermRegistry.fit(tabId)
      xtermRegistry.focus(tabId)
    }, 150)
    return () => {
      clearTimeout(t0)
      clearTimeout(t1)
      xtermRegistry.detachFrom(tabId, 'full')
    }
  }, [tabId, isHost])

  // ResizeObserver: only the active host refits.
  useEffect(() => {
    if (!isHost || !containerRef.current) return
    const el = containerRef.current
    const ro = typeof ResizeObserver !== 'undefined'
      ? new ResizeObserver(() => xtermRegistry.fit(tabId))
      : null
    ro?.observe(el)
    return () => ro?.disconnect()
  }, [tabId, isHost])

  // Right-click paste and drag-drop — full panel only.
  useEffect(() => {
    if (!isHost || !containerRef.current) return
    const container = containerRef.current

    const writeClip = (text: string): void => { void window.pathly?.clipboard?.write(text) }
    const readClip = (cb: (text: string) => void): void => {
      void window.pathly?.clipboard?.read().then(cb)
    }

    let savedSel = ''
    const handleMouseDown = (e: MouseEvent): void => {
      if (e.button === 2) savedSel = xtermRegistry.getSelection(tabId)
    }

    const handleContextMenu = (e: MouseEvent): void => {
      e.preventDefault()
      const sel = savedSel || xtermRegistry.getSelection(tabId)
      savedSel = ''
      if (sel) {
        writeClip(sel)
      } else {
        readClip((text) => void window.pathly?.terminal?.write(tabId, text))
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
  }, [tabId, isHost])

  return (
    <div
      ref={containerRef}
      className={active ? styles.tabViewActive : styles.tabViewHidden}
    />
  )
}
