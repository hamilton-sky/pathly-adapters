import { useEffect, useRef, useState } from 'react'
import { Maximize2, Minimize2, ExternalLink, X } from 'lucide-react'
import { useTheme } from '../../useTheme'
import { useTerminalStore } from '../../store/terminalStore'
import * as xtermRegistry from '../Terminal/xtermRegistry'
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

/**
 * Mini xterm peek inside the chat panel. Shares one xterm instance per tabId
 * with the full terminal panel via xtermRegistry — only one host can own the
 * DOM at a time. Mutual-exclusion rule: if the full panel is currently
 * showing this tab, the card auto-collapses to a banner preview. When the
 * full panel hides or switches away, the card auto-restores to peek if the
 * user had it expanded.
 */
export function MiniTerminalCard({
  tabId,
  target,
  status,
  previewLines,
  onOpenFullTerminal,
  onClose,
}: MiniTerminalCardProps): JSX.Element {
  const t = useTheme()
  const [userViewState, setUserViewState] = useState<ViewState>('peek')
  const [focused, setFocused] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Mutual-exclusion check: is the full terminal panel currently displaying this tab?
  const fullPanelOpen = useTerminalStore((s) => s.open)
  const activeLeft = useTerminalStore((s) => s.activeTabIdLeft)
  const activeRight = useTerminalStore((s) => s.activeTabIdRight)
  const fullShowingThisTab = fullPanelOpen && (activeLeft === tabId || activeRight === tabId)

  const targetColor = TARGET_COLORS[target]
  const previewLine = previewLines[previewLines.length - 1] ?? ''

  // Card hosts the live xterm iff the user wants peek AND the full panel
  // isn't currently showing this tab. The peek button is only meaningful
  // while the card can actually host.
  const cardHosts = userViewState === 'peek' && !fullShowingThisTab
  const allowToggle = !fullShowingThisTab

  // Attach / detach the shared xterm based on host state.
  useEffect(() => {
    if (!cardHosts || !containerRef.current) {
      xtermRegistry.detachFrom(tabId, 'card')
      return
    }
    xtermRegistry.getOrCreate(tabId, { fontSize: 12 })
    xtermRegistry.attachTo(tabId, 'card', containerRef.current, { fontSize: 12 })
    // Two-pass fit handles monospace webfont loading delay at mount.
    // minCols=40 prevents word-per-line wrap in narrow chat panels.
    const t0 = setTimeout(() => xtermRegistry.fit(tabId, 40), 0)
    const t1 = setTimeout(() => xtermRegistry.fit(tabId, 40), 150)
    return () => {
      clearTimeout(t0)
      clearTimeout(t1)
      xtermRegistry.detachFrom(tabId, 'card')
    }
  }, [tabId, cardHosts])

  // ResizeObserver: only refit while card is the host.
  useEffect(() => {
    if (!cardHosts || !containerRef.current) return
    const el = containerRef.current
    const ro = typeof ResizeObserver !== 'undefined'
      ? new ResizeObserver(() => xtermRegistry.fit(tabId, 40))
      : null
    ro?.observe(el)
    return () => ro?.disconnect()
  }, [tabId, cardHosts])

  const statusDotClass = `${styles.statusDot} ${
    status === 'running'
      ? styles.statusDotRunning
      : status === 'done'
        ? styles.statusDotDone
        : styles.statusDotError
  }`

  const statusLabel = fullShowingThisTab
    ? 'in full terminal'
    : status === 'running'
      ? 'interactive'
      : status === 'done'
        ? 'attached'
        : 'error'

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
        <div className={styles.meta}>
          <span className={styles.targetLabel} style={{ color: targetColor }}>
            {target}
          </span>
          <div className={statusDotClass} />
          <span className={styles.statusText}>{statusLabel}</span>
          <span className={styles.tabMeta}>{tabId.slice(-8)}</span>
        </div>

        <div className={styles.icons}>
          {allowToggle && (
            <button
              className={styles.iconBtn}
              onClick={() => setUserViewState((s) => (s === 'peek' ? 'banner' : 'peek'))}
              type="button"
              title={userViewState === 'peek' ? 'Collapse' : 'Expand'}
            >
              {userViewState === 'peek' ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
            </button>
          )}
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

      {/* Peek area — only renders height when card hosts the live xterm.
          The container div stays in the tree so the registry can reparent
          back into it cleanly when the card becomes host again. */}
      <div style={{ height: cardHosts ? 132 : 0, overflow: 'hidden', paddingLeft: 4 }}>
        <div
          ref={containerRef}
          className={styles.terminal}
          onClick={() => xtermRegistry.focus(tabId)}
        />
      </div>

      {/* Banner preview row — visible whenever the card is not hosting */}
      {!cardHosts && (
        <div className={styles.preview}>
          {previewLine ? (
            <span
              className={styles.previewLine}
              style={{ borderLeft: `3px solid ${targetColor}`, paddingLeft: 8 }}
            >
              {previewLine}
            </span>
          ) : (
            <span className={`${styles.previewLine} ${styles.empty}`}>
              {fullShowingThisTab ? 'live view in full terminal' : 'waiting...'}
            </span>
          )}
        </div>
      )}
    </div>
  )
}
