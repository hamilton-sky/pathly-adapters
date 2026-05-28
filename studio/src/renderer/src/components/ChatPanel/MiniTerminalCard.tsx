import { useEffect, useRef, useState } from 'react'
import { Maximize2, Minimize2, ExternalLink, X } from 'lucide-react'
import { Terminal as XTerm } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { useTheme } from '../../useTheme'
import { darkTheme } from '../../theme'
import { useTerminalStore } from '../../store/terminalStore'
import styles from './MiniTerminalCard.module.css'

type ViewState = 'banner' | 'peek'

interface MiniTerminalCardProps {
  tabId: string
  target: 'claude' | 'codex' | 'shell'
  status: 'running' | 'done' | 'error'
  previewLines: string[]
  onOpenFullTerminal: () => void
  onClose: () => void
}

const TARGET_COLORS: Record<MiniTerminalCardProps['target'], string> = {
  claude: '#38BDF8',
  codex: '#F59E0B',
  shell: '#86EFAC',
}

// Terminal is always dark — same convention as TerminalTabView
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

export function MiniTerminalCard({
  tabId,
  target,
  status,
  previewLines,
  onOpenFullTerminal,
  onClose,
}: MiniTerminalCardProps): JSX.Element {
  const t = useTheme()
  const [viewState, setViewState] = useState<ViewState>('banner')
  const [focused, setFocused] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const xtermRef = useRef<XTerm | null>(null)
  const fitAddonRef = useRef<FitAddon | null>(null)
  // Tracks how many scrollback chunks have been written to xterm
  const writtenRef = useRef(0)

  // Subscribe to the scrollback store — avoids IPC listener conflict with TerminalTabView
  const scrollback = useTerminalStore((s) => s.scrollbackByTabId[tabId] ?? [])

  const targetColor = TARGET_COLORS[target]
  const previewLine = previewLines[previewLines.length - 1] ?? ''
  const isPeek = viewState === 'peek'

  // Mount xterm once — write initial scrollback snapshot, no raw IPC onData listener
  useEffect(() => {
    if (!containerRef.current) return

    const xterm = new XTerm({
      theme: xtermTheme() as any,
      fontSize: 12,
      fontFamily: "'Cascadia Code', 'JetBrains Mono', 'Fira Code', monospace",
      cursorBlink: true,
      cursorStyle: 'bar',
      lineHeight: 1.2,
      scrollback: 3000,
    })

    const fitAddon = new FitAddon()
    xterm.loadAddon(fitAddon)
    xtermRef.current = xterm
    fitAddonRef.current = fitAddon
    xterm.open(containerRef.current)

    // Replay all scrollback that exists at mount time, then scroll to current cursor
    const initChunks = useTerminalStore.getState().scrollbackByTabId[tabId] ?? []
    for (const chunk of initChunks) {
      xterm.write(chunk)
    }
    writtenRef.current = initChunks.length
    xterm.scrollToBottom()

    const fit = (): void => {
      try {
        fitAddon.fit()
        // Sync PTY dimensions so TUI apps (Claude Code, Codex) render within
        // the mini card's actual row count instead of the default 80×24.
        void window.pathly?.terminal?.resize(tabId, xterm.cols, xterm.rows)
      } catch { /* ignore transient layout failures */ }
    }

    // Keyboard input → PTY write (outbound only, no inbound IPC listener here)
    const disposeOnData = xterm.onData((data: string) => {
      void window.pathly?.terminal?.write(tabId, data)
    })

    const resizeObserver =
      typeof ResizeObserver !== 'undefined' ? new ResizeObserver(() => fit()) : null
    resizeObserver?.observe(containerRef.current)
    setTimeout(fit, 0)

    return () => {
      resizeObserver?.disconnect()
      disposeOnData.dispose()
      xterm.dispose()
      xtermRef.current = null
      fitAddonRef.current = null
      writtenRef.current = 0
    }
  }, [tabId]) // eslint-disable-line react-hooks/exhaustive-deps

  // Live update — write new chunks and scroll to bottom so cursor is always visible
  useEffect(() => {
    const xterm = xtermRef.current
    if (!xterm) return
    const newChunks = scrollback.slice(writtenRef.current)
    if (newChunks.length === 0) return
    for (const chunk of newChunks) {
      xterm.write(chunk)
    }
    writtenRef.current = scrollback.length
    xterm.scrollToBottom()
  }, [scrollback])

  const statusDotClass = `${styles.statusDot} ${
    status === 'running'
      ? styles.statusDotRunning
      : status === 'done'
        ? styles.statusDotDone
        : styles.statusDotError
  }`

  const statusLabel =
    status === 'running' ? 'interactive' : status === 'done' ? 'attached' : 'error'

  return (
    <div
      className={`${styles.card} ${focused ? styles.cardFocused : ''}`}
      style={{ background: t.bgMantle, border: `1px solid ${t.bgSurface0}`, color: t.textSecondary }}
      tabIndex={0}
      onFocus={() => setFocused(true)}
      onBlur={() => setFocused(false)}
    >
      {/* Header row — two-zone layout */}
      <div className={styles.header}>
        {/* Meta zone: truncates when narrow */}
        <div className={styles.meta}>
          <span className={styles.targetLabel} style={{ color: targetColor }}>
            {target}
          </span>
          <div className={statusDotClass} />
          <span className={styles.statusText}>{statusLabel}</span>
          <span className={styles.tabMeta}>{tabId.slice(-8)}</span>
        </div>

        {/* Icons zone: never shrinks */}
        <div className={styles.icons}>
          <button
            className={styles.iconBtn}
            onClick={() => setViewState(isPeek ? 'banner' : 'peek')}
            type="button"
            title={isPeek ? 'Collapse' : 'Expand'}
          >
            {isPeek ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
          </button>
          <button
            className={styles.iconBtn}
            onClick={onOpenFullTerminal}
            type="button"
            title="Open full terminal"
          >
            <ExternalLink size={13} />
          </button>
          <button
            className={styles.iconBtn}
            onClick={onClose}
            type="button"
            title="Hide"
          >
            <X size={13} />
          </button>
        </div>
      </div>

      {/* Clip wrapper: 0-height in BANNER, 132px in PEEK.
          4px left padding keeps column-0 chars away from the card border-radius clip.
          containerRef div always keeps 132px so FitAddon has stable dimensions. */}
      <div style={{ height: isPeek ? 132 : 0, overflow: 'hidden', paddingLeft: 4 }}>
        <div
          ref={containerRef}
          className={styles.terminal}
          onClick={() => xtermRef.current?.focus()}
        />
      </div>

      {/* Preview row — visible only in BANNER state */}
      {!isPeek && (
        <div className={styles.preview}>
          {previewLine ? (
            <span
              className={styles.previewLine}
              style={{ borderLeft: `3px solid ${targetColor}`, paddingLeft: 8 }}
            >
              {previewLine}
            </span>
          ) : (
            <span className={`${styles.previewLine} ${styles.empty}`}>waiting...</span>
          )}
        </div>
      )}
    </div>
  )
}
