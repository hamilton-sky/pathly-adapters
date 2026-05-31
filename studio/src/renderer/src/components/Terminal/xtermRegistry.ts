import { Terminal as XTerm } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { darkTheme } from '../../theme'

export type HostId = 'card' | 'full' | 'popout'

interface XtermRecord {
  xterm: XTerm
  fitAddon: FitAddon
  currentHost: HostId | null
  hostEl: HTMLDivElement | null
  dataDisposer: { dispose: () => void } | null
  ptyUnsubscribe: (() => void) | null
}

const records = new Map<string, XtermRecord>()

// Terminal is always dark — same convention as TerminalTabView used to enforce
function xtermTheme(): Record<string, string> {
  const t = darkTheme
  return {
    background:          t.bgTerminal,
    foreground:          t.textPrimary,
    cursor:              t.accent,
    cursorAccent:        t.bgTerminal,
    selectionBackground: t.bgSurface1,
    selectionForeground: t.textPrimary,
    black:               t.bgMantle,
    red:                 t.red,
    green:               t.green,
    yellow:              t.yellow,
    blue:                t.blue,
    magenta:             t.accent,
    cyan:                '#67e8f9',
    white:               '#cdd6f4',
    brightBlack:         t.textMuted,
    brightRed:           '#fca5a5',
    brightGreen:         '#86efac',
    brightYellow:        '#fde68a',
    brightBlue:          '#93c5fd',
    brightMagenta:       '#c4b5fd',
    brightCyan:          '#a5f3fc',
    brightWhite:         '#f5f5ff',
  }
}

export function getOrCreate(tabId: string, opts: { fontSize?: number } = {}): XtermRecord {
  const existing = records.get(tabId)
  if (existing) return existing

  const xterm = new XTerm({
    theme: xtermTheme() as Record<string, string>,
    fontSize: opts.fontSize ?? 14,
    fontFamily: "'Cascadia Code', 'JetBrains Mono', 'Fira Code', monospace",
    cursorBlink: true,
    cursorStyle: 'bar',
    lineHeight: 1.2,
    scrollback: 5000,
  })
  const fitAddon = new FitAddon()
  xterm.loadAddon(fitAddon)

  // Clipboard key handlers — attached once per instance, survives host swaps
  xterm.attachCustomKeyEventHandler((event: KeyboardEvent) => {
    if (event.type !== 'keydown') return true
    const writeClip = (text: string): void => { void window.pathly?.clipboard?.write(text) }
    const readClip = (cb: (text: string) => void): void => {
      void window.pathly?.clipboard?.read().then(cb)
    }
    if (event.ctrlKey && !event.shiftKey && event.key === 'c') {
      const sel = xterm.getSelection()
      if (sel) { writeClip(sel); return false }
      return true
    }
    if (event.ctrlKey && !event.shiftKey && event.key === 'v') {
      void (async () => {
        const imgPath = await window.pathly?.clipboard?.readImagePath()
        if (imgPath) void window.pathly?.terminal?.write(tabId, imgPath)
        // For plain text, let xterm's native paste event handle it via onData
      })()
      return false
    }
    if (event.ctrlKey && event.shiftKey && event.key === 'C') {
      const sel = xterm.getSelection()
      if (sel) writeClip(sel)
      return false
    }
    if (event.ctrlKey && event.shiftKey && event.key === 'V') {
      void (async () => {
        const imgPath = await window.pathly?.clipboard?.readImagePath()
        if (imgPath) void window.pathly?.terminal?.write(tabId, imgPath)
        // For plain text, let xterm's native paste event handle it via onData
      })()
      return false
    }
    return true
  })

  const record: XtermRecord = {
    xterm,
    fitAddon,
    currentHost: null,
    hostEl: null,
    dataDisposer: null,
    ptyUnsubscribe: null,
  }

  // PTY data → xterm. ONE writer for this instance, regardless of host.
  const api = window.pathly?.terminal
  if (api) {
    record.ptyUnsubscribe = api.onData(tabId, (data) => xterm.write(data))
    record.dataDisposer = xterm.onData((data: string) => api.write(tabId, data))
  }

  records.set(tabId, record)
  return record
}

export function attachTo(
  tabId: string,
  host: HostId,
  el: HTMLDivElement,
  opts: { fontSize?: number } = {}
): void {
  const rec = records.get(tabId)
  if (!rec) return

  if (opts.fontSize !== undefined && rec.xterm.options.fontSize !== opts.fontSize) {
    rec.xterm.options.fontSize = opts.fontSize
  }

  if (rec.xterm.element) {
    // Move existing DOM tree to new host
    if (rec.xterm.element.parentElement !== el) el.appendChild(rec.xterm.element)
  } else {
    // First-time mount creates the DOM tree
    rec.xterm.open(el)
  }
  rec.hostEl = el
  rec.currentHost = host
}

export function detachFrom(tabId: string, host: HostId): void {
  const rec = records.get(tabId)
  if (!rec || rec.currentHost !== host) return
  // Note: we do NOT remove the DOM element. The next attachTo will reparent it
  // via appendChild. If no future attach happens, the element stays under its
  // last parent until that parent unmounts — which is the common case here.
  rec.currentHost = null
  rec.hostEl = null
}

export function dispose(tabId: string): void {
  const rec = records.get(tabId)
  if (!rec) return
  rec.dataDisposer?.dispose()
  rec.ptyUnsubscribe?.()
  rec.xterm.dispose()
  records.delete(tabId)
}

export function getHost(tabId: string): HostId | null {
  return records.get(tabId)?.currentHost ?? null
}

export function fit(tabId: string, minCols = 1): void {
  const rec = records.get(tabId)
  if (!rec) return
  try {
    rec.fitAddon.fit()
    const cols = Math.max(minCols, rec.xterm.cols)
    const rows = rec.xterm.rows
    if (cols !== rec.xterm.cols) rec.xterm.resize(cols, rows)
    void window.pathly?.terminal?.resize(tabId, cols, rows)
  } catch { /* ignore transient layout failures */ }
}

export function focus(tabId: string): void {
  records.get(tabId)?.xterm.focus()
}

export function write(tabId: string, text: string): void {
  records.get(tabId)?.xterm.write(text)
}

export function getSelection(tabId: string): string {
  return records.get(tabId)?.xterm.getSelection() ?? ''
}
